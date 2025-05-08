#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import argparse
from collections import defaultdict

class TimingSummary:
    def __init__(self, reports_dir: str):
        self.reports_dir = Path(reports_dir)
        self.timing_data = []
        self.summary = {
            "total_orders": 0,
            "successful_orders": 0,
            "failed_orders": 0,
            "total_duration": 0,
            "average_duration": 0,
            "min_duration": float('inf'),
            "max_duration": 0,
            "step_metrics": defaultdict(lambda: {
                "total_duration": 0,
                "average_duration": 0,
                "min_duration": float('inf'),
                "max_duration": 0,
                "count": 0
            }),
            "batch_metrics": [],
            "orders": []
        }

    def load_timing_data(self):
        """Load timing data from all report files in the directory."""
        if not self.reports_dir.exists():
            print(f"Reports directory not found: {self.reports_dir}")
            return

        batch_info = {
            "batch_id": self.reports_dir.name,
            "start_time": None,
            "end_time": None,
            "total_duration": 0,
            "order_count": 0,
            "successful_orders": 0,
            "failed_orders": 0,
            "orders": []
        }

        # Load individual order reports
        for report_file in self.reports_dir.glob("order_*.json"):
            if "None" in report_file.name:
                continue

            try:
                with open(report_file, 'r') as f:
                    data = json.load(f)
                    self.timing_data.append(data)
                    batch_info["orders"].append(data)

                    # Update batch metrics
                    batch_info["order_count"] += 1
                    if data.get("success", True):
                        batch_info["successful_orders"] += 1
                    else:
                        batch_info["failed_orders"] += 1

                    # Parse timestamps
                    start_time = datetime.fromisoformat(data["flow_start"]).timestamp()
                    end_time = datetime.fromisoformat(data["flow_end"]).timestamp()
                    
                    # Update batch timing
                    if not batch_info["start_time"] or start_time < batch_info["start_time"]:
                        batch_info["start_time"] = start_time
                    if not batch_info["end_time"] or end_time > batch_info["end_time"]:
                        batch_info["end_time"] = end_time

            except Exception as e:
                print(f"Error loading {report_file}: {e}")

        # Calculate batch duration
        if batch_info["start_time"] and batch_info["end_time"]:
            batch_info["total_duration"] = batch_info["end_time"] - batch_info["start_time"]

        if batch_info["order_count"] > 0:
            self.summary["batch_metrics"].append(batch_info)

        if not self.timing_data:
            print(f"No order reports found in {self.reports_dir}")
            return

        print(f"Loaded {len(self.timing_data)} order reports")

    def calculate_metrics(self):
        """Calculate summary metrics from the timing data."""
        if not self.timing_data:
            return

        self.summary["total_orders"] = len(self.timing_data)
        self.summary["successful_orders"] = sum(1 for data in self.timing_data if data.get("success", True))
        self.summary["failed_orders"] = self.summary["total_orders"] - self.summary["successful_orders"]

        # Calculate overall timing metrics
        durations = [float(data.get("total_duration", 0)) for data in self.timing_data]
        if durations:
            self.summary["total_duration"] = sum(durations)
            self.summary["average_duration"] = self.summary["total_duration"] / len(durations)
            self.summary["min_duration"] = min(durations)
            self.summary["max_duration"] = max(durations)

        # Calculate step metrics
        for data in self.timing_data:
            steps = data.get("steps", {})
            for step_name, step_data in steps.items():
                duration = float(step_data.get("duration", 0))
                metrics = self.summary["step_metrics"][step_name]
                
                metrics["total_duration"] += duration
                metrics["count"] += 1
                metrics["min_duration"] = min(metrics["min_duration"], duration)
                metrics["max_duration"] = max(metrics["max_duration"], duration)

        # Calculate averages for each step
        for metrics in self.summary["step_metrics"].values():
            if metrics["count"] > 0:
                metrics["average_duration"] = metrics["total_duration"] / metrics["count"]

        # Sort orders by start time
        self.summary["orders"] = sorted(
            self.timing_data,
            key=lambda x: datetime.fromisoformat(x["flow_start"]).timestamp()
        )

    def generate_report(self, output_dir: Optional[str] = None) -> Dict:
        """Generate the summary report."""
        self.load_timing_data()
        self.calculate_metrics()

        # Convert defaultdict to regular dict for JSON serialization
        self.summary["step_metrics"] = dict(self.summary["step_metrics"])

        # Save JSON report
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            report_name = f"summary_{self.reports_dir.name}.json"
            json_path = output_path / report_name
            with open(json_path, 'w') as f:
                json.dump(self.summary, f, indent=2)
            print(f"JSON summary saved to: {json_path}")

        return self.summary

    def print_human_readable(self):
        """Print a human-readable summary of the report."""
        print("\n=== Timing Summary Report ===")
        print(f"Directory: {self.reports_dir}")
        
        if self.summary["total_orders"] == 0:
            print("\nNo orders found in this directory.")
            return

        print(f"\nOverall Metrics:")
        print(f"Total Orders: {self.summary['total_orders']}")
        print(f"Successful Orders: {self.summary['successful_orders']}")
        print(f"Failed Orders: {self.summary['failed_orders']}")
        print(f"Success Rate: {(self.summary['successful_orders'] / self.summary['total_orders'] * 100):.1f}%")
        print(f"\nTiming Metrics:")
        print(f"Average Duration: {self.summary['average_duration']:.2f}s")
        print(f"Min Duration: {self.summary['min_duration']:.2f}s")
        print(f"Max Duration: {self.summary['max_duration']:.2f}s")
        print(f"Total Duration: {self.summary['total_duration']:.2f}s")

        print("\nStep-by-Step Metrics:")
        for step_name, metrics in sorted(self.summary["step_metrics"].items()):
            print(f"\n{step_name}:")
            print(f"  Average: {metrics['average_duration']:.2f}s")
            print(f"  Min: {metrics['min_duration']:.2f}s")
            print(f"  Max: {metrics['max_duration']:.2f}s")
            print(f"  Total: {metrics['total_duration']:.2f}s")
            print(f"  Count: {metrics['count']}")

        print("\nBatch Metrics:")
        for batch in sorted(self.summary["batch_metrics"], key=lambda x: x["start_time"] if x["start_time"] else 0):
            start_time = datetime.fromtimestamp(batch["start_time"]).strftime("%H:%M:%S")
            print(f"\nBatch: {batch['batch_id']}")
            print(f"  Start Time: {start_time}")
            print(f"  Orders: {batch['order_count']}")
            print(f"  Successful: {batch['successful_orders']}")
            print(f"  Failed: {batch['failed_orders']}")
            print(f"  Duration: {batch['total_duration']:.2f}s")

def main():
    parser = argparse.ArgumentParser(description="Generate timing summary reports")
    parser.add_argument("--reports", required=True, help="Directory containing timing reports to analyze")
    parser.add_argument("--output-dir", help="Directory to save summary reports")
    args = parser.parse_args()

    summary = TimingSummary(args.reports)
    summary.generate_report(args.output_dir)
    summary.print_human_readable()

if __name__ == "__main__":
    main() 