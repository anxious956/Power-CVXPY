# Draft email to Prof. Taylor: the detector for step 3 (not sent)

16 Oct 2026. To be sent by Asmar if she agrees. Short on purpose (review/STEP3_PLAN_REVIEW.md §1).

---

Subject: Step 3 of our plan: which Kalman-filter detector would you like to see?

Dear Prof. Taylor,

For step 3 of the plan we showed you (detection under load and noise, your Kalman filter against a learned
detector, shrinking δ until each fails), we would like to check one choice with you before we build it.

Your MMKF with Pirani et al. (2022) runs at the inverter, in the time domain, on the controller's states, with a
perturbation designed for it. Our relay sits at a line end and sees sequence phasors, and our faults are unbalanced.
We propose to keep the structure of your detector (one filter per hypothesis: normal, and A-G and B-C faults over a
location × resistance grid; the posterior update of your eq. 14; a starter that resets the bank), but on the relay's
measurement model, and to test it alongside the set-membership test of the Geometry paper (the design's own relay
characteristic) and a CNN, all on PSCAD data with the designed δ injected.

Would you accept this as the detector we promised, or would you rather see the original at the inverter?

Best regards,
Asmar

---

Notes for Asmar, not for the email: the step-1 and step-2 results that this builds on, with their limits, are in
results/MULTIBUS.md and REVIEW.md rows 49–50. If he asks about the cost: the three-bus design curtails the inverter's
normal output to ≤ 0.46 pu.
