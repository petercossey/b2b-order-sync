# BigCommerce B2B Order Flow Testing Script

A Python script for testing end-to-end order processing flows in BigCommerce B2B Edition, including storefront, internal APIs, enterprise service layer (ESL), and ERP system integration.

## Getting Started

### Prerequisites

- Python 3.9 or higher
- BigCommerce store with B2B Edition enabled
- API credentials:
  - BigCommerce Store API token
  - BigCommerce B2B API token

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd e2e-b2b-order-flow
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root with your API credentials:
```
BC_STORE_HASH=your_store_hash
BC_ACCESS_TOKEN=your_access_token
B2B_ACCESS_TOKEN=your_b2b_access_token
B2B_STOREFRONT_TOKEN=your_b2b_storefront_token  # Must be generated for customer_id 19 (used in test data)
```

> **Important**: The `B2B_STOREFRONT_TOKEN` must be generated for customer_id 19, which is the customer used in the test data (`cart-payload.json`). This ensures that the storefront verification can access the order data for the test customer.

### Usage

The script supports three modes for order processing:

1. Single Order (default):
```bash
python test_flow.py
# or explicitly
python test_flow.py --mode single
```

2. Sequential Orders:
```bash
python test_flow.py --mode sequential --num-orders 5 --delay 10
```
This will create 5 orders one after another with a 10-second delay between each order.

3. Concurrent Orders:
```bash
python test_flow.py --mode concurrent --num-orders 10 --max-concurrent 3
```
This will create 10 orders with a maximum of 3 running at the same time.

### Command Line Options

#### General Options
- `--reports-dir`: Directory to store timing reports (default: reports)

#### Order Processing Options
- `--mode`: Order processing mode
  - `single`: Process one order (default)
  - `sequential`: Process orders one after another
  - `concurrent`: Process multiple orders simultaneously
- `--num-orders`: Number of orders to process (default: 1)
- `--delay`: Delay between orders in seconds for sequential mode (default: 5)
- `--max-concurrent`: Maximum number of concurrent orders for concurrent mode (default: 3)

#### ESL Retrieval Options
- `--b2b-order`: ESL retrieval method
  - `default`: Manually create B2B order (default)
  - `alt`: Poll for B2B order
- `--max-retries`: Maximum number of retry attempts for polling (default: 6)
- `--retry-delay`: Delay between retries in seconds (default: 5)

### Flow Overview

The script simulates the following order processing flow:

1. Initialize Shopping Cart
2. Place Order
3. Process Order
4. Trigger ESL Retrieval (manual creation or polling)
5. Send to ERP
6. Update B2B Order
7. Storefront Confirmation

The script verifies that orders are visible in the B2B Storefront by:
- Querying the B2B Storefront GraphQL API
- Verifying the presence of required fields (createdAt, updatedAt, companyName)
- Providing detailed logging of the verification process

### Timing Reports

The script generates detailed timing reports for each order, stored in the `reports` directory (configurable via `--reports-dir`). Reports are organized by date and include:
- Order ID
- Flow start and end times
- Total duration
- Step-by-step timing information

Example report structure:
```
reports/
├── 2024-03-21/
│   ├── order_123_10-00-00.json
│   ├── order_124_10-15-30.json
│   └── order_125_11-45-20.json
└── ...
```

Each report file contains detailed timing information for each step in the order flow, helping to identify bottlenecks and measure performance.
