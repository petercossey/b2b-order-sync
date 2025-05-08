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
import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TimingTracker:
    def __init__(self, reports_dir="reports", is_batch=False, batch_start_time=None):
        self.reports_dir = reports_dir
        self.is_batch = is_batch
        self.batch_start_time = batch_start_time or datetime.now()
        self.start_time = None
        self.end_time = None
        self.steps = {}
        self.current_step = None
        self.current_step_start = None
        self.order_id = None
        self.order_number = None

    def start_flow(self, order_id=None, order_number=None):
        """Start timing the entire flow."""
        self.start_time = datetime.now()
        self.order_id = order_id
        self.order_number = order_number
        logger.info(f"Starting timing for {'batch' if self.is_batch else 'single'} order flow")

    def start_step(self, step_name):
        """Start timing a specific step."""
        if self.current_step:
            self.end_step()
        self.current_step = step_name
        self.current_step_start = datetime.now()
        logger.info(f"Starting step: {step_name}")

    def end_step(self):
        """End timing for the current step."""
        if self.current_step and self.current_step_start:
            duration = (datetime.now() - self.current_step_start).total_seconds()
            self.steps[self.current_step] = {
                "start": self.current_step_start.isoformat(),
                "end": datetime.now().isoformat(),
                "duration": duration
            }
            logger.info(f"Completed step: {self.current_step} (Duration: {duration:.2f}s)")
            self.current_step = None
            self.current_step_start = None

    def end_flow(self):
        """End timing the entire flow and save the report."""
        self.end_time = datetime.now()
        if self.current_step:
            self.end_step()
        
        total_duration = (self.end_time - self.start_time).total_seconds()
        logger.info(f"Completed order flow (Total Duration: {total_duration:.2f}s)")

        # Create report data
        report_data = {
            "order_id": self.order_id,
            "order_number": self.order_number,
            "flow_start": self.start_time.isoformat(),
            "flow_end": self.end_time.isoformat(),
            "total_duration": total_duration,
            "steps": self.steps
        }

        # Determine report directory structure
        if self.is_batch:
            # For batch tests, use batch_YYYY-MM-DD_HH-MM-SS format
            batch_dir = f"batch_{self.batch_start_time.strftime('%Y-%m-%d_%H-%M-%S')}"
            report_dir = os.path.join(self.reports_dir, batch_dir)
        else:
            # For single orders, use YYYY-MM-DD format
            date_dir = self.start_time.strftime("%Y-%m-%d")
            report_dir = os.path.join(self.reports_dir, date_dir)

        # Create directory if it doesn't exist
        os.makedirs(report_dir, exist_ok=True)

        # Generate filename with order number and timestamp
        timestamp = self.start_time.strftime("%H-%M-%S")
        filename = f"order_{self.order_number}_{timestamp}.json" if self.order_number else f"order_{self.order_id}_{timestamp}.json"
        
        # Save report
        report_path = os.path.join(report_dir, filename)
        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=2)
        
        logger.info(f"Timing report saved to: {report_path}")
        return report_path

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

    async def load_test_data(self, filename: str) -> Dict[str, Any]:
        """Load test data from a JSON file"""
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

    async def create_cart(self, session: aiohttp.ClientSession) -> Dict[str, Any]:
        """Create a new cart using test data"""
        try:
            payload = await self.load_test_data('cart-payload.json')
            url = f"{self.bc_base_url}/v3/carts"
            
            async with session.post(url, headers=self.bc_headers, json=payload) as response:
                response.raise_for_status()
                cart_data = await response.json()
                logger.info(f"Successfully created cart with ID: {cart_data['data']['id']}")
                return cart_data['data']
                
        except aiohttp.ClientError as e:
            logger.error(f"Error creating cart: {str(e)}")
            raise

    async def add_shipping_address(self, session: aiohttp.ClientSession, cart_id: str) -> Dict[str, Any]:
        """Add shipping address to the cart and get shipping options"""
        try:
            shipping_address = await self.load_test_data('checkout-shipping-address.json')
            
            # First get the cart to get line item IDs
            cart_url = f"{self.bc_base_url}/v3/carts/{cart_id}"
            async with session.get(cart_url, headers=self.bc_headers) as response:
                response.raise_for_status()
                cart_data = await response.json()
            
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
            
            async with session.post(url, headers=self.bc_headers, params=params, json=payload) as response:
                response.raise_for_status()
                consignment_data = await response.json()
                logger.info(f"Successfully added shipping address and got shipping options")
                return consignment_data['data']
                
        except aiohttp.ClientError as e:
            logger.error(f"Error adding shipping address: {str(e)}")
            raise

    async def update_shipping_option(self, session: aiohttp.ClientSession, cart_id: str, consignment_id: str, shipping_option_id: str) -> Dict[str, Any]:
        """Update the shipping option for a consignment"""
        try:
            url = f"{self.bc_base_url}/v3/checkouts/{cart_id}/consignments/{consignment_id}"
            payload = {
                "shipping_option_id": shipping_option_id
            }
            
            async with session.put(url, headers=self.bc_headers, json=payload) as response:
                response.raise_for_status()
                consignment_data = await response.json()
                logger.info(f"Successfully updated shipping option")
                return consignment_data['data']
                
        except aiohttp.ClientError as e:
            logger.error(f"Error updating shipping option: {str(e)}")
            raise

    async def add_billing_address(self, session: aiohttp.ClientSession, cart_id: str) -> Dict[str, Any]:
        """Add billing address to the checkout"""
        try:
            billing_address = await self.load_test_data('checkout-billing-address.json')
            
            url = f"{self.bc_base_url}/v3/checkouts/{cart_id}/billing-address"
            async with session.post(url, headers=self.bc_headers, json=billing_address) as response:
                response.raise_for_status()
                billing_data = await response.json()
                logger.info(f"Successfully added billing address")
                return billing_data['data']
                
        except aiohttp.ClientError as e:
            logger.error(f"Error adding billing address: {str(e)}")
            raise

    async def create_order(self, session: aiohttp.ClientSession, cart_id: str) -> Dict[str, Any]:
        """Create an order from the checkout"""
        try:
            url = f"{self.bc_base_url}/v3/checkouts/{cart_id}/orders"
            async with session.post(url, headers=self.bc_headers) as response:
                response.raise_for_status()
                order_data = await response.json()
                logger.info(f"Successfully created order with ID: {order_data['data']['id']}")
                return order_data['data']
                
        except aiohttp.ClientError as e:
            logger.error(f"Error creating order: {str(e)}")
            raise

    async def update_order_status(self, session: aiohttp.ClientSession, order_id: int) -> Dict[str, Any]:
        """Update the order status to 'Awaiting Fulfillment'"""
        try:
            url = f"{self.bc_base_url}/v2/orders/{order_id}"
            payload = {
                "status_id": 11  # 11 is the status ID for "Awaiting Fulfillment"
            }
            
            async with session.put(url, headers=self.bc_headers, json=payload) as response:
                response.raise_for_status()
                order_data = await response.json()
                logger.info(f"Successfully updated order {order_id} status to Awaiting Fulfillment")
                return order_data
                
        except aiohttp.ClientError as e:
            logger.error(f"Error updating order status: {str(e)}")
            raise

    async def poll_b2b_order(self, session: aiohttp.ClientSession, order_id: int, max_retries: int = 6, delay_seconds: int = 5) -> Dict[str, Any]:
        """Poll the B2B Orders API for a specific order with retry logic"""
        for attempt in range(max_retries):
            try:
                url = f"{self.b2b_base_url}/orders/{order_id}"
                async with session.get(url, headers=self.b2b_headers) as response:
                    if response.status == 200:
                        order_data = await response.json()
                        logger.info(f"Successfully retrieved B2B order {order_id} on attempt {attempt + 1}")
                        return order_data
                    elif response.status == 404:
                        if attempt < max_retries - 1:
                            logger.info(f"B2B order {order_id} not found yet. Attempt {attempt + 1} of {max_retries}. Retrying in {delay_seconds} seconds...")
                            await asyncio.sleep(delay_seconds)
                            continue
                        else:
                            raise Exception(f"B2B order {order_id} not found after {max_retries} attempts")
                    else:
                        response.raise_for_status()
                        
            except aiohttp.ClientError as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Error polling B2B order (attempt {attempt + 1}): {str(e)}")
                    await asyncio.sleep(delay_seconds)
                else:
                    logger.error(f"Failed to retrieve B2B order after {max_retries} attempts: {str(e)}")
                    raise

    async def get_order_details(self, session: aiohttp.ClientSession, order_id: int) -> Dict[str, Any]:
        """Get order details from v2 Orders API"""
        try:
            url = f"{self.bc_base_url}/v2/orders/{order_id}"
            async with session.get(url, headers=self.bc_headers) as response:
                response.raise_for_status()
                order_data = await response.json()
                logger.info(f"Successfully retrieved order {order_id} details")
                return order_data
                
        except aiohttp.ClientError as e:
            logger.error(f"Error retrieving order details: {str(e)}")
            raise

    async def create_b2b_order(self, session: aiohttp.ClientSession, order_id: int, customer_id: int) -> Dict[str, Any]:
        """Manually create a B2B order using the B2B Orders API"""
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
            
            async with session.post(url, headers=self.b2b_headers, json=payload) as response:
                response.raise_for_status()
                b2b_order = await response.json()
                logger.info(f"Successfully created B2B order for BC order {order_id}")
                return b2b_order
                
        except aiohttp.ClientError as e:
            logger.error(f"Error creating B2B order: {str(e)}")
            raise

    async def send_to_erp(self, b2b_order: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate sending order data to ERP system and receiving a response"""
        logger.info(f"Simulating sending order {b2b_order.get('id')} to ERP system")
        
        # Simulate processing delay
        await asyncio.sleep(0.4)
        
        # Generate mock ERP response
        erp_response = {
            "poNumber": f"PO-{b2b_order.get('id')}-{int(time.time())}",
            "extraField1": "ERP_PROCESSED"
        }
        
        logger.info(f"Received mock ERP response for order {b2b_order.get('id')}")
        return erp_response

    async def update_b2b_order(self, session: aiohttp.ClientSession, order_id: int, erp_response: Dict[str, Any]) -> Dict[str, Any]:
        """Update B2B order with ERP response data"""
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
            
            async with session.put(url, headers=self.b2b_headers, json=payload) as response:
                response.raise_for_status()
                updated_order = await response.json()
                logger.info(f"Successfully updated B2B order {order_id} with ERP data")
                return updated_order
                
        except aiohttp.ClientError as e:
            logger.error(f"Error updating B2B order: {str(e)}")
            raise

    async def verify_storefront_order(self, session: aiohttp.ClientSession, order_id: int) -> Dict[str, Any]:
        """Verify that the order is visible in the B2B Storefront GraphQL API"""
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
                "bcOrderId": order_id
            }
            
            # Make the GraphQL request
            payload = {
                "query": query,
                "variables": variables
            }
            
            async with session.post(url, headers=headers, json=payload) as response:
                response.raise_for_status()
                result = await response.json()
            
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
            
        except aiohttp.ClientError as e:
            logger.error(f"Error verifying order in B2B Storefront API: {str(e)}")
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
    """Process a single order through the complete flow"""
    order_prefix = f"Order {order_number}: " if order_number is not None else ""
    
    try:
        async with aiohttp.ClientSession() as session:
            # Create cart
            timing.start_step('create_cart')
            cart = await test_flow.create_cart(session)
            cart_id = cart['id']
            timing.end_step()
            
            # Add shipping address and get shipping options
            timing.start_step('add_shipping_address')
            consignment_data = await test_flow.add_shipping_address(session, cart_id)
            consignment_id = consignment_data['consignments'][0]['id']
            timing.end_step()
            
            # Get the first available shipping option
            shipping_option_id = consignment_data['consignments'][0]['available_shipping_options'][0]['id']
            
            # Update shipping option
            timing.start_step('update_shipping_option')
            await test_flow.update_shipping_option(session, cart_id, consignment_id, shipping_option_id)
            timing.end_step()
            
            # Add billing address
            timing.start_step('add_billing_address')
            await test_flow.add_billing_address(session, cart_id)
            timing.end_step()
            
            # Create order
            timing.start_step('create_order')
            order = await test_flow.create_order(session, cart_id)
            order_id = order['id']
            timing.order_id = order_id
            timing.end_step()
            logger.info(f"{order_prefix}Order created successfully with ID: {order_id}")
            
            # Update order status to Awaiting Fulfillment
            timing.start_step('update_order_status')
            updated_order = await test_flow.update_order_status(session, order_id)
            timing.end_step()
            logger.info(f"{order_prefix}Order {order_id} status updated successfully")
            
            # Handle ESL retrieval based on selected method
            timing.start_step('esl_retrieval')
            if b2b_order_mode == 'default':
                logger.info(f"{order_prefix}Using default ESL retrieval method (manual B2B order creation)")
                order_details = await test_flow.get_order_details(session, order_id)
                customer_id = order_details['customer_id']
                b2b_order = await test_flow.create_b2b_order(session, order_id, customer_id)
                logger.info(f"{order_prefix}B2B order created successfully")
            else:
                logger.info(f"{order_prefix}Using alternative ESL retrieval method (polling)")
                logger.info(f"{order_prefix}Polling configuration: max_retries={max_retries}, delay={retry_delay}s")
                b2b_order = await test_flow.poll_b2b_order(
                    session,
                    order_id,
                    max_retries=max_retries,
                    delay_seconds=retry_delay
                )
                logger.info(f"{order_prefix}B2B order {order_id} retrieved successfully")
            timing.end_step()
            
            # Send order to ERP
            timing.start_step('erp_processing')
            logger.info(f"{order_prefix}Starting ERP simulation for order {order_id}")
            erp_response = await test_flow.send_to_erp(b2b_order)
            logger.info(f"{order_prefix}ERP simulation completed for order {order_id}")
            logger.info(f"{order_prefix}ERP response: {erp_response}")
            timing.end_step()
            
            # Update B2B order with ERP response data
            timing.start_step('update_b2b_order')
            logger.info(f"{order_prefix}Updating B2B order {order_id} with ERP data")
            updated_b2b_order = await test_flow.update_b2b_order(session, order_id, erp_response)
            logger.info(f"{order_prefix}B2B order {order_id} updated successfully with ERP data")
            timing.end_step()
            
            # Verify storefront order
            timing.start_step('storefront_verification')
            verification_result = await test_flow.verify_storefront_order(session, order_id)
            logger.info(f"{order_prefix}Storefront verification result: {verification_result}")
            timing.end_step()
            
            # End flow timing
            timing.end_flow()
            
            logger.info(f"{order_prefix}Checkout process completed successfully")
            return {
                'success': True,
                'order_id': order_id,
                'summary': timing.steps
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
    """Process multiple orders sequentially with a delay between each order"""
    test_flow = BCTestFlow()
    results = []
    batch_tracker = TimingTracker(is_batch=True)
    batch_tracker.start_flow()
    
    for i in range(num_orders):
        timing = TimingTracker(is_batch=True, batch_start_time=batch_tracker.start_time)
        timing.start_flow(order_number=i + 1)
        
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
    
    batch_tracker.end_flow()
    return results

async def process_orders_concurrent(
    num_orders: int,
    max_concurrent: int,
    b2b_order_mode: str,
    max_retries: int,
    retry_delay: int,
    reports_dir: str
) -> List[Dict[str, Any]]:
    """Process multiple orders concurrently with a maximum number of concurrent orders"""
    test_flow = BCTestFlow()
    results = []
    
    # Create a semaphore to limit concurrent orders
    semaphore = asyncio.Semaphore(max_concurrent)
    batch_tracker = TimingTracker(is_batch=True)
    batch_tracker.start_flow()
    
    async def process_with_semaphore(order_number: int):
        async with semaphore:
            timing = TimingTracker(is_batch=True, batch_start_time=batch_tracker.start_time)
            timing.start_flow(order_number=order_number)
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
    batch_tracker.end_flow()
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