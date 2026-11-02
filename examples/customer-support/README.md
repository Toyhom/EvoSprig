# Customer support

**Help customers resolve order problems, with a person in control of refunds.**

The assistant looks up an order and suggests a response. Refund requests pause for approval; an approved request goes to your order service.

## Connect your store

Set `DEEPSEEK_API_KEY` and configure the two HTTP bindings in `deployment.example.yaml`: `support.lookup` for order details and `support.refund` for a refund. Set the service token named in the profile. Your order service enforces refund eligibility and honors idempotency keys.

```bash
evosprig serve --project examples/customer-support/agent.yaml \
  --profile examples/customer-support/deployment.example.yaml \
  --workspace .evosprig/support --studio-dir apps/studio/dist
```

In Studio, enable writes for the run and enter `{"order_id":"YOUR_ORDER_ID","question":"I would like to cancel this order."}`. Review the proposed action in History before continuing.

## Make it yours

Edit `prompts/policy.md` for your store's tone and rules. Add shipping or inventory tools, or change the workflow to route different requests to different teams. The graph uses EvoSprig's conditions, approval nodes and durable tool execution.
