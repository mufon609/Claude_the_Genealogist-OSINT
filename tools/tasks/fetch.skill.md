# One page saved by a model

You are the launcher: a subagent does the task, and code judges what it did. You write no prompt and change none.

1. Get the task. Run `python3 tools/run_task.py next --model <model>`, with the model you were told to use (`haiku` when
   you were told none). It prints `agent:`, `model:` and `prompt:`; the prompt is every line after the `prompt:` line, to
   the end of the output.
2. Spawn the subagent `{agent}` on the model printed, with exactly that prompt: nothing added, nothing left out, nothing
   reworded. Run one subagent, once. The browser asks the owner to approve what it does; the approval is theirs, so wait
   for it and never work around it.
3. Report it done. When the subagent has ended, run
   `python3 tools/run_task.py done --answer '<its last message, as it came>' --tokens <N> --tool-uses <N> --duration-ms <N> --by "agent:<your session> for user:<owner>"`
   with the numbers you were given for the subagent. Leave `--answer` out when it ended with no message, and leave out
   any number you were not given.
4. Say what `done` printed, as it printed it. The outcome is what code found in the folder, never what the subagent said.

One task per run of this skill. Do not open the page yourself, do not save it yourself, and do not run the task again
when the outcome is not the one hoped for: say what was printed and stop.
