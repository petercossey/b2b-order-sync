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

The script generates detailed timing reports for each order, stored in the `reports` directory (configurable via `--reports-dir`). Reports are organized differently based on the processing mode:

1. Single Order Mode:
```
reports/
├── 2024-03-21/
│   ├── order_123_10-00-00.json
│   └── order_124_10-15-30.json
└── ...
```

2. Batch Mode (Sequential or Concurrent):
```
reports/
├── batch_2024-03-21_14-30-00/
│   ├── order_1_14-30-05.json
│   ├── order_2_14-30-15.json
│   └── order_3_14-30-25.json
└── ...
```

Each report file contains:
- Order ID and number
- Flow start and end times
- Total duration
- Step-by-step timing information

The batch mode reports are organized in a dedicated directory named with the batch start time, making it easy to analyze the performance of multiple orders processed together. This structure helps in:
- Comparing performance across different batch runs
- Analyzing the impact of concurrent processing
- Tracking the timing of individual orders within a batch
- Identifying bottlenecks in batch processing

### Analyzing Timing Reports

The `generate_summary.py` script provides a detailed analysis of timing reports for a specific batch or directory of reports.

#### Usage

```bash
python generate_summary.py --reports <reports-directory> [--output-dir <output-directory>]
```

Example:
```bash
# Analyze a specific batch directory
python generate_summary.py --reports reports/batch_2024-03-21_14-30-00

# Save the summary to a specific output directory
python generate_summary.py --reports reports/batch_2024-03-21_14-30-00 --output-dir summaries
```

#### Command Line Options

- `--reports`: Directory containing timing reports to analyze (required)
- `--output-dir`: Directory to save the summary report (optional)

#### Summary Report Contents

The script generates a comprehensive summary including:

1. Overall Metrics:
   - Total number of orders
   - Success/failure counts
   - Success rate
   - Average, minimum, and maximum durations

2. Step-by-Step Metrics:
   - Average duration per step
   - Minimum and maximum durations
   - Total time spent in each step
   - Number of executions

3. Batch Metrics:
   - Batch start time
   - Number of orders
   - Success/failure counts
   - Total batch duration

The summary is displayed in a human-readable format and can be saved as a JSON file for further analysis.
