# Customer support with approval

An order-support workflow combines the tool and human-review patterns used in [LangGraph](https://github.com/langchain-ai/langgraph): look up an order, propose an action, route refund requests to a human, then perform an authorized write.

```bash
python examples/customer-support/run_demo.py --workspace .evosprig/support-approved --scenario approved
python examples/customer-support/run_demo.py --workspace .evosprig/support-denied --scenario denied
python examples/customer-support/run_demo.py --workspace .evosprig/support-answer --scenario answer
```

The included transactional order service is a fixture. It validates refund amounts independently of the model, permits one refund per order and checks idempotency keys. The denied and answer-only paths create no refund. Add `--live` to use the configured model while keeping the fixture order service.

To connect your business system, implement `support.lookup` and `support.refund` using the schemas in `deployment.example.yaml`. Enforce eligibility, authorization and idempotency in that service. Use Studio's History page for real human decisions; the demo's `--scenario` option supplies its review response automatically.
