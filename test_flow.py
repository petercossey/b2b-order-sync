#!/usr/bin/env python3

import os
import json
import logging
import requests
import argparse
from dotenv import load_dotenv
from typing import Dict, Any, Optional, List
import time
from datetime import datetime
import pathlib
import asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TimingTracker:
    def __init__(self):
        self.steps = {}
        self.start_time = None
        self.end_time = None
        self.order_id = None

    def set_order_id(self, order_id: int):
        """Set the order ID for report naming"""
        self.order_id = order_id

    def start_step(self, step_name: str):
        """Record the start time of a step"""
        self.steps[step_name] = {
            'start': datetime.now(),
            'end': None,
            'duration': None
        }

    def end_step(self, step_name: str):
        """Record the end time of a step and calculate duration"""
        if step_name in self.steps:
            self.steps[step_name]['end'] = datetime.now()
            duration = self.steps[step_name]['end'] - self.steps[step_name]['start']
            self.steps[step_name]['duration'] = duration.total_seconds()

    def start_flow(self):
        """Record the start time of the entire flow"""
        self.start_time = datetime.now()

    def end_flow(self):
        """Record the end time of the entire flow"""
        self.end_time = datetime.now()

    def generate_summary(self) -> Dict[str, Any]:
        """Generate a summary of all timing information"""
        if not self.start_time or not self.end_time:
            return {}

        total_duration = (self.end_time - self.start_time).total_seconds()
        
        summary = {
            'flow_start': self.start_time.isoformat(),
            'flow_end': self.end_time.isoformat(),
            'total_duration_seconds': total_duration,
            'order_id': self.order_id,
            'steps': {}
        }

        for step_name, timing in self.steps.items():
            summary['steps'][step_name] = {
                'start': timing['start'].isoformat(),
                'end': timing['end'].isoformat() if timing['end'] else None,
                'duration_seconds': timing['duration']
            }

        return summary

    def save_report(self, output_dir: str = 'reports'):
        """Save the timing report to disk"""
        if not self.start_time or not self.end_time:
            logger.warning("Cannot save report: flow timing not complete")
            return

        # Create reports directory if it doesn't exist
        reports_dir = pathlib.Path(output_dir)
        reports_dir.mkdir(parents=True, exist_ok=True)

        # Create date-based subdirectory
        date_dir = reports_dir / self.start_time.strftime('%Y-%m-%d')
        date_dir.mkdir(exist_ok=True)

        # Generate filename with timestamp and order ID
        timestamp = self.start_time.strftime('%H-%M-%S')
        filename = f"order_{self.order_id}_{timestamp}.json"
        filepath = date_dir / filename

        # Generate and save the report
        summary = self.generate_summary()
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Timing report saved to: {filepath}")

class BCTestFlow:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Store API credentials
        self.store_hash = os.getenv('BC_STORE_HASH')
        self.access_token = os.getenv('BC_ACCESS_TOKEN')
        self.b2b_access_token = os.getenv('B2B_ACCESS_TOKEN')
        
        # Validate required environment variables
        if not all([self.store_hash, self.access_token, self.b2b_access_token]):
            raise ValueError("Missing required environment variables. Please check your .env file.")
        
        # Set up base URLs
        self.bc_base_url = f"https://api.bigcommerce.com/stores/{self.store_hash}"
        self.b2b_base_url = "https://api-b2b.bigcommerce.com/api/v3/io"
        
        # Set up headers
        self.bc_headers = {
            'X-Auth-Token': self.access_token,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        self.b2b_headers = {
            'authToken': self.b2b_access_token,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def load_test_data(self, filename: str) -> Dict[str, Any]:
        """
        Load test data from a JSON file
        """
        try:
            file_path = os.path.join('test-data', filename)
            with open(file_path, 'r') as f:
                data = json.load(f)
            logger.info(f"Successfully loaded test data from {filename}")
            return data
        except FileNotFoundError:
            logger.error(f"Test data file not found: {filename}")
            raise
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in test data file: {filename}")
            raise

    def create_cart(self) -> Dict[str, Any]:
        """
        Create a new cart using test data and return the cart data
        """
        try:
            # Load cart payload from test data
            payload = self.load_test_data('cart-payload.json')
            
            url = f"{self.bc_base_url}/v3/carts"
            response = requests.post(url, headers=self.bc_headers, json=payload)
            response.raise_for_status()
            
            cart_data = response.json()
            logger.info(f"Successfully created cart with ID: {cart_data['data']['id']}")
            return cart_data['data']
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating cart: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response details: {e.response.text}")
            raise

    def add_shipping_address(self, cart_id: str) -> Dict[str, Any]:
        """
        Add shipping address to the cart and get shipping options
        """
        try:
            shipping_address = self.load_test_data('checkout-shipping-address.json')
            
            # First get the cart to get line item IDs
            cart_url = f"{self.bc_base_url}/v3/carts/{cart_id}"
            cart_response = requests.get(cart_url, headers=self.bc_headers)
            cart_response.raise_for_status()
            cart_data = cart_response.json()
            
            # Get the first physical item ID
            line_item_id = cart_data['data']['line_items']['physical_items'][0]['id']
            
            # Add shipping address with line item
            url = f"{self.bc_base_url}/v3/checkouts/{cart_id}/consignments"
            params = {
                'include': 'consignments.available_shipping_options'
            }
            
            payload = [
                {
                    "shipping_address": shipping_address,
                    "line_items": [
                        {
                            "item_id": line_item_id,
                            "quantity": 1
                        }
                    ]
                }
            ]
            
            response = requests.post(url, headers=self.bc_headers, params=params, json=payload)
            response.raise_for_status()
            
            consignment_data = response.json()
            logger.info(f"Successfully added shipping address and got shipping options")
            return consignment_data['data']
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error adding shipping address: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response details: {e.response.text}")
            raise

    def update_shipping_option(self, cart_id: str, consignment_id: str, shipping_option_id: str) -> Dict[str, Any]:
        """
        Update the shipping option for a consignment
        """
        try:
            url = f"{self.bc_base_url}/v3/checkouts/{cart_id}/consignments/{consignment_id}"
            payload = {
                "shipping_option_id": shipping_option_id
            }
            
            response = requests.put(url, headers=self.bc_headers, json=payload)
            response.raise_for_status()
            
            consignment_data = response.json()
            logger.info(f"Successfully updated shipping option")
            return consignment_data['data']
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error updating shipping option: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response details: {e.response.text}")
            raise

    def add_billing_address(self, cart_id: str) -> Dict[str, Any]:
        """
        Add billing address to the checkout
        """
        try:
            billing_address = self.load_test_data('checkout-billing-address.json')
            
            url = f"{self.bc_base_url}/v3/checkouts/{cart_id}/billing-address"
            response = requests.post(url, headers=self.bc_headers, json=billing_address)
            response.raise_for_status()
            
            billing_data = response.json()
            logger.info(f"Successfully added billing address")
            return billing_data['data']
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error adding billing address: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response details: {e.response.text}")
            raise

    def create_order(self, cart_id: str) -> Dict[str, Any]:
        """
        Create an order from the checkout
        """
        try:
            url = f"{self.bc_base_url}/v3/checkouts/{cart_id}/orders"
            response = requests.post(url, headers=self.bc_headers)
            response.raise_for_status()
            
            order_data = response.json()
            logger.info(f"Successfully created order with ID: {order_data['data']['id']}")
            return order_data['data']
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating order: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response details: {e.response.text}")
            raise

    def update_order_status(self, order_id: int) -> Dict[str, Any]:
        """
        Update the order status to 'Awaiting Fulfillment'
        """
        try:
            url = f"{self.bc_base_url}/v2/orders/{order_id}"
            payload = {
                "status_id": 11  # 11 is the status ID for "Awaiting Fulfillment"
            }
            
            response = requests.put(url, headers=self.bc_headers, json=payload)
            response.raise_for_status()
            
            order_data = response.json()
            logger.info(f"Successfully updated order {order_id} status to Awaiting Fulfillment")
            return order_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error updating order status: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response details: {e.response.text}")
            raise

    def poll_b2b_order(self, order_id: int, max_retries: int = 6, delay_seconds: int = 5) -> Dict[str, Any]:
        """
        Poll the B2B Orders API for a specific order with retry logic
        
        Args:
            order_id: The ID of the order to poll for
            max_retries: Maximum number of retry attempts (default: 6)
            delay_seconds: Delay between retries in seconds (default: 5)
            
        Returns:
            Dict containing the B2B order data if found
            
        Raises:
            Exception: If order is not found after max retries
        """
        for attempt in range(max_retries):
            try:
                url = f"{self.b2b_base_url}/orders/{order_id}"
                response = requests.get(url, headers=self.b2b_headers)
                
                if response.status_code == 200:
                    order_data = response.json()
                    logger.info(f"Successfully retrieved B2B order {order_id} on attempt {attempt + 1}")
                    return order_data
                elif response.status_code == 404:
                    if attempt < max_retries - 1:
                        logger.info(f"B2B order {order_id} not found yet. Attempt {attempt + 1} of {max_retries}. Retrying in {delay_seconds} seconds...")
                        time.sleep(delay_seconds)
                        continue
                    else:
                        raise Exception(f"B2B order {order_id} not found after {max_retries} attempts")
                else:
                    response.raise_for_status()
                    
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Error polling B2B order (attempt {attempt + 1}): {str(e)}")
                    time.sleep(delay_seconds)
                else:
                    logger.error(f"Failed to retrieve B2B order after {max_retries} attempts: {str(e)}")
                    if hasattr(e.response, 'text'):
                        logger.error(f"Response details: {e.response.text}")
                    raise

    def get_order_details(self, order_id: int) -> Dict[str, Any]:
        """
        Get order details from v2 Orders API
        
        Args:
            order_id: The ID of the order to retrieve
            
        Returns:
            Dict containing the order data
            
        Raises:
            Exception: If order retrieval fails
        """
        try:
            url = f"{self.bc_base_url}/v2/orders/{order_id}"
            response = requests.get(url, headers=self.bc_headers)
            response.raise_for_status()
            
            order_data = response.json()
            logger.info(f"Successfully retrieved order {order_id} details")
            return order_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving order details: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response details: {e.response.text}")
            raise

    def create_b2b_order(self, order_id: int, customer_id: int) -> Dict[str, Any]:
        """
        Manually create a B2B order using the B2B Orders API
        
        Args:
            order_id: The BC order ID to create B2B order for
            customer_id: The customer ID from the BC order
            
        Returns:
            Dict containing the created B2B order data
            
        Raises:
            Exception: If B2B order creation fails
        """
        try:
            url = f"{self.b2b_base_url}/orders"
            payload = {
                "bcOrderId": order_id,
                "customerId": customer_id,
                "extraFields": [
                    {
                        "fieldName": "Delivery Instructions",
                        "fieldValue": "TBD"
                    }
                ]
            }
            
            response = requests.post(url, headers=self.b2b_headers, json=payload)
            response.raise_for_status()
            
            b2b_order = response.json()
            logger.info(f"Successfully created B2B order for BC order {order_id}")
            return b2b_order
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating B2B order: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response details: {e.response.text}")
            raise

    def send_to_erp(self, b2b_order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate sending order data to ERP system and receiving a response
        
        Args:
            b2b_order: The B2B order data to send to ERP
            
        Returns:
            Dict containing mock ERP response data
        """
        logger.info(f"Simulating sending order {b2b_order.get('id')} to ERP system")
        
        # Simulate processing delay
        time.sleep(0.4)
        
        # Generate mock ERP response
        erp_response = {
            "poNumber": f"PO-{b2b_order.get('id')}-{int(time.time())}",
            "extraField1": "ERP_PROCESSED"
        }
        
        logger.info(f"Received mock ERP response for order {b2b_order.get('id')}")
        return erp_response

    def update_b2b_order(self, order_id: int, erp_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update B2B order with ERP response data
        
        Args:
            order_id: The ID of the order to update
            erp_response: The ERP response data containing poNumber and extraField1
            
        Returns:
            Dict containing the updated B2B order data
        """
        try:
            url = f"{self.b2b_base_url}/orders/{order_id}"
            
            # Prepare the update payload
            payload = {
                "bcOrderId": order_id,
                "customerId": 19,  # Hardcoded as specified
                "poNumber": erp_response["poNumber"],
                "extraFields": [
                    {
                        "fieldName": "Delivery Instructions",
                        "fieldValue": erp_response["extraField1"]
                    }
                ]
            }
            
            response = requests.put(url, headers=self.b2b_headers, json=payload)
            response.raise_for_status()
            
            updated_order = response.json()
            logger.info(f"Successfully updated B2B order {order_id} with ERP data")
            return updated_order
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error updating B2B order: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response details: {e.response.text}")
            raise

    def verify_storefront_order(self, order_id: int) -> Dict[str, Any]:
        """
        Verify that the order is visible in the B2B Storefront GraphQL API
        
        Args:
            order_id: The ID of the order to verify
            
        Returns:
            Dict containing the verification results
            
        Raises:
            Exception: If the verification fails
        """
        try:
            # Get the storefront token from environment
            storefront_token = os.getenv('B2B_STOREFRONT_TOKEN')
            if not storefront_token:
                raise ValueError("B2B_STOREFRONT_TOKEN environment variable is not set")

            # Set up GraphQL endpoint and headers
            url = "https://api-b2b.bigcommerce.com/graphql"
            headers = {
                'Authorization': f'Bearer {storefront_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }

            # Construct the GraphQL query
            query = """
            query AllOrders($bcOrderId: Decimal!) {
                allOrders(bcOrderId: $bcOrderId) {
                    totalCount
                    edges {
                        cursor
                        node {
                            id
                            createdAt
                            updatedAt
                            bcOrderId
                            companyName
                        }
                    }
                }
            }
            """
            
            # Set up the variables for the query
            variables = {
                "bcOrderId": order_id  # Send as integer instead of string
            }
            
            # Make the GraphQL request
            payload = {
                "query": query,
                "variables": variables
            }
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            # Check if we got any data
            if not result.get('data', {}).get('allOrders', {}).get('edges'):
                logger.warning(f"Order {order_id} not found in B2B Storefront API")
                return {
                    "success": False,
                    "message": "Order not found in B2B Storefront API",
                    "data": None
                }
            
            # Get the order data from the first edge
            order_data = result['data']['allOrders']['edges'][0]['node']
            
            # Verify the required fields
            verification_result = {
                "success": True,
                "message": "Order found in B2B Storefront API",
                "data": {
                    "createdAt": order_data.get('createdAt'),
                    "updatedAt": order_data.get('updatedAt'),
                    "companyName": order_data.get('companyName')
                }
            }
            
            logger.info(f"Successfully verified order {order_id} in B2B Storefront API")
            logger.info(f"Verification details: {json.dumps(verification_result, indent=2)}")
            
            return verification_result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error verifying order in B2B Storefront API: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response details: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during storefront verification: {str(e)}")
            raise

async def process_single_order(
    test_flow: BCTestFlow,
    timing: TimingTracker,
    b2b_order_mode: str,
    max_retries: int,
    retry_delay: int,
    reports_dir: str,
    order_number: Optional[int] = None
) -> Dict[str, Any]:
    """
    Process a single order through the complete flow
    
    Args:
        test_flow: BCTestFlow instance
        timing: TimingTracker instance
        b2b_order_mode: ESL retrieval method ('default' or 'alt')
        max_retries: Maximum number of retry attempts for polling
        retry_delay: Delay between retries in seconds
        reports_dir: Directory to store timing reports
        order_number: Optional order number for logging (used in multi-order scenarios)
    
    Returns:
        Dict containing the order results
    """
    order_prefix = f"Order {order_number}: " if order_number is not None else ""
    
    try:
        # Create cart
        timing.start_step('create_cart')
        cart = test_flow.create_cart()
        cart_id = cart['id']
        timing.end_step('create_cart')
        
        # Add shipping address and get shipping options
        timing.start_step('add_shipping_address')
        consignment_data = test_flow.add_shipping_address(cart_id)
        consignment_id = consignment_data['consignments'][0]['id']
        timing.end_step('add_shipping_address')
        
        # Get the first available shipping option
        shipping_option_id = consignment_data['consignments'][0]['available_shipping_options'][0]['id']
        
        # Update shipping option
        timing.start_step('update_shipping_option')
        test_flow.update_shipping_option(cart_id, consignment_id, shipping_option_id)
        timing.end_step('update_shipping_option')
        
        # Add billing address
        timing.start_step('add_billing_address')
        test_flow.add_billing_address(cart_id)
        timing.end_step('add_billing_address')
        
        # Create order
        timing.start_step('create_order')
        order = test_flow.create_order(cart_id)
        order_id = order['id']
        timing.set_order_id(order_id)
        timing.end_step('create_order')
        logger.info(f"{order_prefix}Order created successfully with ID: {order_id}")
        
        # Update order status to Awaiting Fulfillment
        timing.start_step('update_order_status')
        updated_order = test_flow.update_order_status(order_id)
        timing.end_step('update_order_status')
        logger.info(f"{order_prefix}Order {order_id} status updated successfully")
        
        # Handle ESL retrieval based on selected method
        timing.start_step('esl_retrieval')
        if b2b_order_mode == 'default':
            logger.info(f"{order_prefix}Using default ESL retrieval method (manual B2B order creation)")
            order_details = test_flow.get_order_details(order_id)
            customer_id = order_details['customer_id']
            b2b_order = test_flow.create_b2b_order(order_id, customer_id)
            logger.info(f"{order_prefix}B2B order created successfully")
        else:
            logger.info(f"{order_prefix}Using alternative ESL retrieval method (polling)")
            logger.info(f"{order_prefix}Polling configuration: max_retries={max_retries}, delay={retry_delay}s")
            b2b_order = test_flow.poll_b2b_order(
                order_id,
                max_retries=max_retries,
                delay_seconds=retry_delay
            )
            logger.info(f"{order_prefix}B2B order {order_id} retrieved successfully")
        timing.end_step('esl_retrieval')
        
        # Send order to ERP
        timing.start_step('erp_processing')
        logger.info(f"{order_prefix}Starting ERP simulation for order {order_id}")
        erp_response = test_flow.send_to_erp(b2b_order)
        logger.info(f"{order_prefix}ERP simulation completed for order {order_id}")
        logger.info(f"{order_prefix}ERP response: {erp_response}")
        timing.end_step('erp_processing')
        
        # Update B2B order with ERP response data
        timing.start_step('update_b2b_order')
        logger.info(f"{order_prefix}Updating B2B order {order_id} with ERP data")
        updated_b2b_order = test_flow.update_b2b_order(order_id, erp_response)
        logger.info(f"{order_prefix}B2B order {order_id} updated successfully with ERP data")
        timing.end_step('update_b2b_order')
        
        # Verify storefront order
        timing.start_step('storefront_verification')
        verification_result = test_flow.verify_storefront_order(order_id)
        logger.info(f"{order_prefix}Storefront verification result: {verification_result}")
        timing.end_step('storefront_verification')
        
        # End flow timing
        timing.end_flow()
        
        # Generate and log timing summary
        summary = timing.generate_summary()
        logger.info(f"{order_prefix}Timing Summary:")
        logger.info(json.dumps(summary, indent=2))
        
        # Save report to disk
        timing.save_report(reports_dir)
        
        logger.info(f"{order_prefix}Checkout process completed successfully")
        return {
            'success': True,
            'order_id': order_id,
            'summary': summary
        }
        
    except Exception as e:
        logger.error(f"{order_prefix}Error in checkout process: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

async def process_orders_sequential(
    num_orders: int,
    delay_seconds: int,
    b2b_order_mode: str,
    max_retries: int,
    retry_delay: int,
    reports_dir: str
) -> List[Dict[str, Any]]:
    """
    Process multiple orders sequentially with a delay between each order
    """
    test_flow = BCTestFlow()
    results = []
    
    for i in range(num_orders):
        timing = TimingTracker()
        timing.start_flow()
        
        result = await process_single_order(
            test_flow,
            timing,
            b2b_order_mode,
            max_retries,
            retry_delay,
            reports_dir,
            order_number=i + 1
        )
        results.append(result)
        
        if i < num_orders - 1:  # Don't delay after the last order
            logger.info(f"Waiting {delay_seconds} seconds before next order...")
            await asyncio.sleep(delay_seconds)
    
    return results

async def process_orders_concurrent(
    num_orders: int,
    max_concurrent: int,
    b2b_order_mode: str,
    max_retries: int,
    retry_delay: int,
    reports_dir: str
) -> List[Dict[str, Any]]:
    """
    Process multiple orders concurrently with a maximum number of concurrent orders
    """
    test_flow = BCTestFlow()
    results = []
    
    # Create a semaphore to limit concurrent orders
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_with_semaphore(order_number: int):
        async with semaphore:
            timing = TimingTracker()
            timing.start_flow()
            return await process_single_order(
                test_flow,
                timing,
                b2b_order_mode,
                max_retries,
                retry_delay,
                reports_dir,
                order_number=order_number
            )
    
    # Create tasks for all orders
    tasks = [
        process_with_semaphore(i + 1)
        for i in range(num_orders)
    ]
    
    # Wait for all tasks to complete
    results = await asyncio.gather(*tasks)
    return results

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Test BigCommerce API flow')
    parser.add_argument('--b2b-order', choices=['default', 'alt'], default='default',
                      help='ESL retrieval method: default (manual B2B order creation) or alt (polling)')
    parser.add_argument('--max-retries', type=int, default=6,
                      help='Maximum number of retry attempts for B2B order polling (default: 6)')
    parser.add_argument('--retry-delay', type=int, default=5,
                      help='Delay between retries in seconds for B2B order polling (default: 5)')
    parser.add_argument('--reports-dir', type=str, default='reports',
                      help='Directory to store timing reports (default: reports)')
    
    # Add new arguments for multiple order processing
    parser.add_argument('--num-orders', type=int, default=1,
                      help='Number of orders to process (default: 1)')
    parser.add_argument('--mode', choices=['single', 'sequential', 'concurrent'], default='single',
                      help='Order processing mode (default: single)')
    parser.add_argument('--delay', type=int, default=5,
                      help='Delay between orders in seconds for sequential mode (default: 5)')
    parser.add_argument('--max-concurrent', type=int, default=3,
                      help='Maximum number of concurrent orders for concurrent mode (default: 3)')
    
    args = parser.parse_args()

    try:
        if args.mode == 'single':
            # Process a single order
            timing = TimingTracker()
            timing.start_flow()
            asyncio.run(process_single_order(
                BCTestFlow(),
                timing,
                args.b2b_order,
                args.max_retries,
                args.retry_delay,
                args.reports_dir
            ))
        elif args.mode == 'sequential':
            # Process orders sequentially
            logger.info(f"Processing {args.num_orders} orders sequentially with {args.delay}s delay")
            results = asyncio.run(process_orders_sequential(
                args.num_orders,
                args.delay,
                args.b2b_order,
                args.max_retries,
                args.retry_delay,
                args.reports_dir
            ))
            # Log summary of results
            successful = sum(1 for r in results if r['success'])
            logger.info(f"Completed {len(results)} orders: {successful} successful, {len(results) - successful} failed")
        else:  # concurrent mode
            # Process orders concurrently
            logger.info(f"Processing {args.num_orders} orders concurrently (max {args.max_concurrent} at a time)")
            results = asyncio.run(process_orders_concurrent(
                args.num_orders,
                args.max_concurrent,
                args.b2b_order,
                args.max_retries,
                args.retry_delay,
                args.reports_dir
            ))
            # Log summary of results
            successful = sum(1 for r in results if r['success'])
            logger.info(f"Completed {len(results)} orders: {successful} successful, {len(results) - successful} failed")
            
    except Exception as e:
        logger.error(f"Error in main process: {str(e)}")
        raise

if __name__ == "__main__":
    main() 