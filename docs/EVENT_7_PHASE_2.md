# Event 7 Phase 2 Documentation

## Overview
Event 7 Phase 2 is the question-answering phase of the collective obedience event. After Phase 1 (where users click the "Woof" button to opt-in), Phase 2 tests participants' knowledge with a randomly selected question.

## How It Works

### Phase 2 Trigger
- Phase 2 automatically starts after Phase 1 completes (when the threshold of 10+ button clicks is reached)
- The bot waits 2 seconds after role assignment to ensure all roles are properly distributed
- Phase 2 begins in channel `1450628852345868369` (EVENT_PHASE2_CHANNEL_ID)

### Question Selection
- A random question is selected from a pool of 20+ questions using `secrets.choice()` for cryptographically secure randomization
- Questions cover topics like:
  - Isla's programs (Isla Rebrand, Isla Hearts, IslaWare, Isla.exe, IslaOS, Slots)
  - Pricing information ($15, $20, $30)
  - Personal preferences (favorite drink, color, anime, character, gaming genre)
  - Platform information (Windows)
  - Nicknames and titles (dogs, pups, puppies, goddess)
  - Dates (founding month/year, launch dates)

### Answer Format
- Answers can be:
  - **Single string**: Exact match (case-insensitive)
  - **List of strings**: Any one of the listed answers is accepted
- Examples:
  - `"steam"` - Single answer
  - `["level drain", "draining level", "draining levels"]` - Multiple accepted variations
  - `["13/12/2025", "12/13/2025"]` - Date format variations

### User Interaction
1. **Channel**: Users must answer in channel `1450628852345868369`
2. **One Answer Per User**: Each user can only submit one answer during Phase 2
3. **Answer Processing**: 
   - Bot checks if the user's message contains any of the accepted answers (case-insensitive)
   - Answer matching is done via substring matching (e.g., "steam" matches "steam", "steam.exe", etc.)

### Rewards & Penalties

#### Correct Answer
- **XP Reward**: +50 XP
- **Role Assignment**: Immediately receives the **Success Role** (`1450285064943571136`)
- **Visual Feedback**: Bot adds a ❤️ heart reaction to the user's message
- **Access**: User gains access to the success channel for Phase 3

#### Incorrect Answer
- **XP Penalty**: -50 XP
- **No Role**: User does not receive the success role
- **Phase 3**: User will receive the failure role at the end of Phase 2

### Time Limit
- **Duration**: 1 minute (60 seconds)
- After 1 minute, Phase 2 ends automatically
- No more answers are accepted after the timer expires

### Phase 2 End & Phase 3 Transition
When Phase 2 ends (after 1 minute):
1. **Role Assignment**:
   - Users who answered correctly already have the Success Role
   - Users who answered incorrectly or didn't answer receive the Failure Role (`1450285246019928104`)
2. **Phase 3 Start**:
   - Bot waits 10 seconds before starting Phase 3 messages
   - Phase 3 only starts if there are users in the respective categories:
     - If no failed users → No punishment event
     - If no successful users → No reward event
3. **Channel Access**:
   - Success Role users → Access to success channel (`1450329916146057266`)
   - Failure Role users → Access to failure channel (`1450329944549752884`)

## Technical Details

### Channel Configuration
- **Phase 2 Channel**: `1450628852345868369` (EVENT_PHASE2_CHANNEL_ID)
- This channel is **NOT** an XP-tracked channel, but the bot can read and message in it

### Role IDs
- **Opt-In Role**: `1450589443152023583` (EVENT_7_OPT_IN_ROLE) - Required to participate
- **Success Role**: `1450285064943571136` (EVENT_7_SUCCESS_ROLE) - Assigned immediately on correct answer
- **Failure Role**: `1450285246019928104` (EVENT_7_FAILED_ROLE) - Assigned at Phase 2 end for incorrect/no answer

### XP Rewards
- **Correct Answer**: +50 XP (EVENT_REWARDS[7]["phase2_correct"])
- **Incorrect Answer**: -50 XP (EVENT_REWARDS[7]["phase2_wrong"])

### Question Pool
The question pool includes 20+ questions with various answer formats:
- Single answer questions (e.g., "What program does Isla Rebrand affect?" → "steam")
- Multiple accepted answers (e.g., "What's the main theme of Isla Hearts?" → ["level drain", "draining level", "draining levels"])
- Date variations (e.g., "When did IslaOS 2.0 launch?" → ["13/12/2025", "12/13/2025"])

### Embed Format
Phase 2 question embed:
- **Description**: `"Good. Now answer me.\n\n*{question}*"`
- **Image**: `"https://i.imgur.com/v8Ik4cS.png"`
- **Color**: `0x2F3136` (consistent with all event embeds)

## User Flow Example

1. **Phase 1**: User clicks "Woof" button → Receives Opt-In Role
2. **Phase 2 Starts**: Bot posts question in Phase 2 channel
3. **User Answers**: User types answer in Phase 2 channel
4. **Immediate Feedback**:
   - If correct: ❤️ reaction + Success Role + +50 XP
   - If incorrect: -50 XP (no role yet)
5. **Timer Expires**: After 1 minute, Phase 2 ends
6. **Role Assignment**: Incorrect/no-answer users receive Failure Role
7. **Phase 3**: Users are separated into success/failure channels based on their roles

## Error Handling
- If user already answered: Bot ignores subsequent messages from that user
- If channel not found: Bot logs error and skips Phase 2
- If role assignment fails: Bot logs error but continues with event
- If message processing fails: Bot logs error but doesn't crash

## Notes
- Phase 2 answers are processed regardless of whether the channel is configured for XP tracking
- The bot uses `resolve_channel_id()` to handle Discord threads properly
- Answer matching is case-insensitive and uses substring matching
- Users can only answer once per Phase 2 event
- The 1-minute timer is strict - no answers accepted after expiration


