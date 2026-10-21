# Coleshill Town match monitor

Free hosted match checks with ready-to-post X drafts. Your computer and iPhone can be switched off while checks run. Nothing is posted to X automatically, and no X API key or paid AI service is used.

Every match tweet draft carries **Live At Pack Meadow | @PackMeadow**, the Pack Meadow Facebook link and `#ColeshillTown`. This is the coverage brand on both home and away updates. Long drafts are split to retain the information and branding within the character limit.

Copy uses consistent matchday formatting: an energetic **GOAL, COLESHILL!** for a verified Coleshill scorer, neutral opposition goal notices, clear HALF-TIME/FULL-TIME headings and restrained substitution/discipline updates. No invented descriptions of finishes, crowd reactions or match dominance are added.

## On your iPhone

1. Install the free **GitHub** app and sign in as the repository owner.
2. Allow GitHub notifications in iPhone Settings. In GitHub's notification settings, enable push notifications for mentions and assignments.
3. On this repository, choose **Watch → All Activity**. Each match gets an issue; new drafts appear as comments mentioning you. You can also read drafts under the repository's **Issues** tab.
4. Open a draft notification, tap **Open in X**, check the text and the account, then tap **Post**. If X opens in Safari, sign in or copy the draft into the X app.

Notifications depend on GitHub and your iPhone settings. A workflow can create a draft successfully even if push notifications are disabled or delayed. Drafts and source links are public in this public repository.

## Match coverage

### Player goal graphics

Twenty supplied player graphics are stored unchanged under `graphics/`, including their sponsor details. A Coleshill goal draft includes the matching image and a full-size link when the feed's scorer name exactly matches a registered graphic and that player is listed in the Coleshill line-up/substitutes. The confirmed Benjamin Usher-Shipway / Ben Usher-Shipway spelling variation is supported. Unknown names, opposition scorers and own goals receive no player graphic rather than an incorrect one.

On iPhone, open the graphic and save it to Photos, then open the X draft and attach the image before posting. The X draft link fills in text only; it cannot attach the image automatically. Additional players can be added to `graphics/players.json` with their graphic and verified name variations.

### Times and events

- **Saturdays:** 14:00–17:30, Europe/London, including automatic GMT/BST handling.
- **Monday–Friday:** only on a listed Coleshill Town match day, from one hour before the confirmed kick-off until two hours thirty minutes after it.
- The scheduler's UTC envelope is 11:00–23:55 Monday–Saturday. Unusually early weekday games outside that envelope are not covered. Sunday games are not included.
- Checks are scheduled every five minutes. GitHub may delay or skip scheduled jobs, so this is best-effort coverage rather than instant commentary.
- Reads the Football Web Pages Coleshill fixture list and match pages. This includes midweek cup matches when listed. The NPL site is not used as an automatic fallback because its feed has not been validated for this purpose.
- Generates Coleshill line-ups/substitutes, goals by either side, substitutions, cautions, dismissals, explicit half-time/full-time updates and listed postponements when available in the source. It never invents a scorer, kick-off, half-time or full-time from elapsed time.
- Multiple events can arrive between checks. Goal drafts label the score **Latest score**, which may include later goals in the same batch. Feed corrections are flagged for review.
- Line-up text is split into multiple drafts when necessary to stay within 280 characters. Review lineup completeness against the source before posting.

## Cost and operation

Standard GitHub-hosted Linux Actions runners are free for public repositories. This workflow uses only standard runners and Python's standard library. Keep the repository public and do not enable paid runners or paid add-ons. You do not need to enter billing details for this monitor.

The first code push tests the parser and verifies access to a recent and upcoming match from GitHub's servers. Scheduled runs then create drafts during the requested windows. Use **Actions → Coleshill match monitor → Run workflow** for a manual check. A manual run still respects match windows and does not replay old matches.

Deduplication state is committed to `state.json`. Every comment has a unique marker so a failed state commit does not ordinarily repeat the same draft. Football Web Pages changes, outages, a disabled Actions workflow, or GitHub API failures can interrupt coverage. Failures are visible in the Actions tab.

GitHub can disable scheduled workflows in public repositories after 60 days without repository activity. State commits normally keep this repository active, but check the Actions tab after long breaks. To pause, disable the workflow there.

## Local checks

```sh
python3 -m unittest -v
python3 monitor.py --check-source
python3 monitor.py --dry-run
```

`--dry-run` does not post comments or save state. Normal execution needs the automatically supplied `GH_TOKEN`, `GITHUB_REPOSITORY` and `GITHUB_REPOSITORY_OWNER` environment variables from GitHub Actions. Never put personal access tokens or passwords in repository files.
