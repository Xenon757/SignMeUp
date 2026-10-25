# Chrome Web Store listing

Text and answers for the Chrome Web Store developer dashboard. Upload `signmeup-extension.zip`
(made with `npm run package`).

## Store listing

**Name:** SignMeUp: ASL for YouTube

**Summary** (from the manifest, 132 characters max):
Signs YouTube videos in ASL with an animated signer, from the video's own captions.

**Category:** Accessibility

**Language:** English

**Description:**

SignMeUp signs YouTube videos in American Sign Language while you watch. An animated signer
appears in a corner of the player and signs what's being said, alongside the captions.

How it works
- It uses the video's own English captions, so there's nothing to upload and nothing to wait for:
  signing starts within a couple of seconds, even on long videos.
- Each sign is animated from a real ASL dictionary video from ASL Signbank (CC BY-NC-SA 4.0), a
  lexical database run by sign language researchers.
- Words without a sign are fingerspelled, shown as a row of handshape cards.
- Turn it on or off from the toolbar button.

Good to know
- It needs English captions (uploaded or auto-generated). Videos without them aren't signed.
- It's an automatic translation of English captions, not a human interpreter: ASL grammar is
  simplified and some signs may be missing or not the best choice. Feedback is welcome.
- The signer is hidden during ads.

SignMeUp is a free, non-commercial project. It has no accounts, ads or analytics.
Website: https://signmeup.fly.dev · Source: https://github.com/Xenon757/SignMeUp

**Privacy policy URL:** https://signmeup.fly.dev/privacy

**Homepage / support URL:** https://github.com/Xenon757/SignMeUp/issues

## Images

- Store icon: `icons/icon128.png` (in the zip).
- Screenshots (required, 1280×800, up to 5): take them on real YouTube videos with the signer showing,
  e.g. the box in the corner mid-sign, a fingerspelled word, and the popup. Google asks that they show
  the actual experience.
- Small promo tile (optional, 440×280): the logo on the site's green, no text.

## Privacy practices tab

**Single purpose:** Show an animated ASL signer on YouTube videos that signs the video's captions.

**Permission justifications:**
- `storage`: remembers whether signing is turned on.
- Host permission `https://signmeup.fly.dev/*`: sends caption text to SignMeUp's server, which
  translates it to signs, and loads each sign's animation from it.
- Content scripts on `https://www.youtube.com/*`: read the current video's captions and draw the
  signer inside the player. One script runs in the page itself because only there can it reach
  YouTube's player to get the captions.

**Remote code:** No. All code is in the package; the server only sends data (signs and animations
as JSON).

**Data usage** (what to tick):
- Website content: yes. The captions of the video being watched are sent to SignMeUp's server to
  be translated. Nothing else is collected: no personally identifiable information, health,
  financial, authentication, personal communications, location, web history or user activity data.
- Certify: not sold to third parties; not used or transferred for purposes unrelated to the single
  purpose; not used to determine creditworthiness or for lending.
