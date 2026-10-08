"""Dependency-free example to verify MetricBox execution and argument handling."""

import argparse
import json
import math


def number_list(value):
    try:
        numbers = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError("请输入 JSON 数值数组") from exc
    if not isinstance(numbers, list) or not numbers:
        raise argparse.ArgumentTypeError("请输入非空数值数组")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item)
           for item in numbers):
        raise argparse.ArgumentTypeError("数组只能包含有限数值")
    return numbers


def main():
    parser = argparse.ArgumentParser(description="MetricBox 示例：计算两个数值列表的 MAE 与 MSE")
    parser.add_argument("--pred", type=number_list, default=[0.1, 0.5, 0.9])
    parser.add_argument("--target", type=number_list, default=[0, 0.5, 1])
    args = parser.parse_args()
    if len(args.pred) != len(args.target):
        parser.error("pred 和 target 的长度必须一致")
    errors = [prediction - target for prediction, target in zip(args.pred, args.target)]
    result = {
        "samples": len(errors),
        "MAE": sum(abs(error) for error in errors) / len(errors),
        "MSE": sum(error ** 2 for error in errors) / len(errors),
    }
    print("指标计算完成", flush=True)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

