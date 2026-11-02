# Backup recording

## Executive summary

`backup-demo.mp4` records a scripted, typed rehearsal using the application's deterministic demo provider and fictional inputs. It demonstrates the software flow; it is not evidence of a fine-tuned model, live cloud speech or participant testing. The final assessed backup should be recorded again after training and real-service evaluation. The recording is edited to approximately 80 seconds (accelerated from a longer capture) and the provider label remains visible in the interview.

## Reproduce

Start an isolated demo API with a test database and production frontend, then run the browser capture script in `e2e/record-demo.mjs`. This script does not use personal interview records. Native model weights are unnecessary for this software-flow backup. Use the timed live script in `DEMO_SCRIPT.md` for the final classroom rehearsal.
