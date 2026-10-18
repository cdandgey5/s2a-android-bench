# [L][User story] Completing / Concluding the challenge / Streak lost and cannot restart

User story

- As a participant who completes 25 days, I want to receive my 15% store discount code and have the option to add a Baby Globe icon applied to my profile, so that the reward feels immediate and satisfying.

- As a participant who did not complete 25 days, I want my best effort recognized and communicated so that I understand what my progress was.

- As a participant whose streak has ended with insufficient days remaining to complete a restart, I want the restart option hidden, so that I'm not misled into an impossible attempt.

Requirements:

Challenge complete:

- When a streak of 25 consecutive days is recorded, the module immediately transitions to State: Challenge complete successfully

- Completion can occur after May 31st: a user who joins May 31st has until June 25th to complete their streak (or June 26th if a streak freeze is applied - see Nice to Have)

- Displays a "Collect your prize" CTA on the Widget

- Tapping "Collect your prize" opens an in-app prize screen

- State persists until July 10th, after which the Widget is removed for all users

- Completion is a terminal state: the system stops listening for article opens once 25 days are reached

Challenge concluded: incomplete

- For users who do not reach 25 days with a streak that started between 1-31 May, but did read for more than 1 day in a row, they should see State: Challenge concluded: incomplete / Streak lost and cannot restart

- Show user's highest streak achieved up until that point

- Persist until July 10th, after which the module is removed for all users

Challenge concluded: Streak lost and cannot restart

- Disallow re-starting the challenge if after May 31
- After May 31st, the system stops listening for new streaks for all enrolled users who have not reached 25 days

- If a user loses their streak after May 31, they should see State: Challenge concluded: incomplete / Streak lost and cannot restart

Challenge concluded: No streak

- For users who never joined, or joined and never read more than 1 day in a row starting with a start date of 1-31 May, they should see State: Challenge concluded: No streak

- Persists until July 10th, after which the module is removed for all users

Prize screen

- Prize screen can be triggered any time from the Challenge completed widget state

- Display prize information on top of Activity Tab

- Offer link to Wikipedia Store: https://store.wikimedia.org/discount/Widget15
- Store link should open in their browser

- User must be logged-in to view prize information

Designs

- State: Challenge complete successfully https://www.figma.com/design/nnXvcESYGNFiMmxYA41vVG/WP25--Apps-Reading-Challenge?node-id=380-2382&t=33Zrff8kZOyR1KaO-4

- State: Challenge concluded: incomplete / Streak lost and cannot restart https://www.figma.com/design/nnXvcESYGNFiMmxYA41vVG/WP25--Apps-Reading-Challenge?node-id=380-2400&t=33Zrff8kZOyR1KaO-4

- State: Challenge concluded: No streak https://www.figma.com/design/nnXvcESYGNFiMmxYA41vVG/WP25--Apps-Reading-Challenge?node-id=380-2417&t=33Zrff8kZOyR1KaO-4

- Prize collection https://www.figma.com/design/nnXvcESYGNFiMmxYA41vVG/WP25--Apps-Reading-Challenge?node-id=405-6626&t=SNhsUDod59JFR2Vw-4
