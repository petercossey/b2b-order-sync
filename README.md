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
B2B_STOREFRONT_TOKEN=your_b2b_storefront_token
```

### Usage

The script supports two modes for ESL (Enterprise Service Layer) order retrieval:

1. Default mode (manual B2B order creation):
```bash
python test_flow.py
# or explicitly
python test_flow.py --b2b-order default
```

2. Alternative mode (polling for B2B order):
```bash
python test_flow.py --b2b-order alt
```

When using the alternative mode, you can configure the polling behavior:
```bash
python test_flow.py --b2b-order alt --max-retries 10 --retry-delay 3
```

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

### Command Line Options

- `--b2b-order`: ESL retrieval method
  - `default`: Manually create B2B order (default)
  - `alt`: Poll for B2B order
- `--max-retries`: Maximum number of retry attempts for polling (default: 6)
- `--retry-delay`: Delay between retries in seconds (default: 5)
