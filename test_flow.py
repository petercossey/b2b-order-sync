#!/usr/bin/env python3

import os
import json
import logging
import requests
from dotenv import load_dotenv
from typing import Dict, Any, Optional
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

def main():
    try:
        # Initialize the test flow
        test_flow = BCTestFlow()
        
        # Create cart
        cart = test_flow.create_cart()
        cart_id = cart['id']
        
        # Add shipping address and get shipping options
        consignment_data = test_flow.add_shipping_address(cart_id)
        consignment_id = consignment_data['consignments'][0]['id']
        
        # Get the first available shipping option
        shipping_option_id = consignment_data['consignments'][0]['available_shipping_options'][0]['id']
        
        # Update shipping option
        test_flow.update_shipping_option(cart_id, consignment_id, shipping_option_id)
        
        # Add billing address
        test_flow.add_billing_address(cart_id)
        
        # Create order
        order = test_flow.create_order(cart_id)
        order_id = order['id']
        logger.info(f"Order created successfully with ID: {order_id}")
        
        # Update order status to Awaiting Fulfillment
        updated_order = test_flow.update_order_status(order_id)
        logger.info(f"Order {order_id} status updated successfully")
        
        # Poll B2B Orders API for the order
        logger.info(f"Starting B2B order polling for order {order_id}")
        b2b_order = test_flow.poll_b2b_order(order_id)
        logger.info(f"B2B order {order_id} retrieved successfully")
        
        # Send order to ERP
        logger.info(f"Starting ERP simulation for order {order_id}")
        erp_response = test_flow.send_to_erp(b2b_order)
        logger.info(f"ERP simulation completed for order {order_id}")
        logger.info(f"ERP response: {erp_response}")
        
        logger.info("Checkout process completed successfully")
        
    except Exception as e:
        logger.error(f"Test flow failed: {str(e)}")
        raise

if __name__ == "__main__":
    main() 