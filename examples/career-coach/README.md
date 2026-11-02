# Career coach

![Workflow in EvoSprig Studio](canvas.png)

Turn a resume and a job description into a tailored application and an interview practice session. Role-fit analysis feeds two parallel writers; the candidate answers a question before receiving feedback.

## An application built from actual experience

For an operations analyst applying to a SQL/Python role, the application produced these resume bullets:

> - Build SQL reports on shipment delays (operations analyst, 2023–present).
> - Cut weekly reporting time from 3 hours to 45 minutes.
> - Wrote a Python script to clean CSV data.
> - Coordinate with four warehouse coordinators on report definitions.

Its interview questions ask how the candidate explained delays, what changed in the reporting process and how the Python script was used. After the candidate responds, the coach identifies the missing example and gives a short practice plan.

## Run it

Set `DEEPSEEK_API_KEY`, or use a [deployment profile](../../docs/deployment.md) for your own model. Open the application in Studio:

```bash
evosprig serve --project examples/career-coach/agent.yaml \
  --studio-dir apps/studio/dist
```

Choose **Live model** and paste the input from `sample.json`. At the practice node, enter your answer in **History** to continue.

## Make it yours

Change the role and resume in `sample.json`. Edit `factual_writing` to set your resume conventions and `interview_coaching` to change the practice method. The factual-writing skill is shared by the reviewer, resume writer and final coach.

For unattended improvement, import an [evaluation suite](../../docs/evaluation.md#bring-your-own-task-suite) with an interview answer in each task's `responses`, such as `{"graph/practice": {"answer": "I automated the weekly report with SQL and Python."}}`. Then select prompt or skill resources and an algorithm in **Improve**. EvoSprig runs the same workflow with each candidate. [Agent configuration](../../docs/agent-resources.md) describes resource selection and model parameters.

Built with EvoSprig's [Python SDK](../build_work_apps.py). Application patterns draw on [Coze community resume workflows](https://github.com/AICoderTudou/coze-workflows/tree/main/coze), with application review and interview practice added here.
