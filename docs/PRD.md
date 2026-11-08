# SignMeUp — Product Requirements

November 7, 2026 · Aadi Belwal

## Summary

SignMeUp signs the speech in a video in American Sign Language with an animated 2D signer, shown next to the captions. It runs as a website for uploaded videos ([signmeup.fly.dev](https://signmeup.fly.dev)) and as a Chrome extension that signs YouTube videos as they play ([Chrome Web Store](https://chromewebstore.google.com/detail/signmeup-asl-for-youtube/jehdimfnbbfahecpbdlchaciioibpkkp)). It began as a team hackathon project (Hello World 2025) and is now a free, non-commercial fork maintained by Aadi Belwal.

## Users

| User | Need | Where they use it |
| --- | --- | --- |
| Deaf and hard of hearing viewers whose first language is ASL (primary) | Follow everyday video in their own language, not only in written English | Extension, on YouTube |
| People learning ASL | See common signs in context while watching normal videos | Extension; compare page |
| Teachers and people sharing their own videos | Add an ASL layer to a clip without hiring an interpreter for every video | Website upload |

It is not for settings that need accuracy: classes, medical, legal or official content still need a human interpreter.

## Problem

Captions are written English, which for many Deaf viewers is a second language. ASL is "a complete, natural language" with its own grammar ([NIDCD](https://www.nidcd.nih.gov/health/american-sign-language)). The median English reading level of deaf and hard of hearing high school graduates in one national study was about fourth grade ([Traxler, 2000](https://doi.org/10.1093/deafed/5.4.337)), though half read above it and researchers warn the figure is often over-simplified ([Marschark](https://www.handsandvoices.org/articles/research/v9-2_marschark.htm)). In one study of 51 sign language users, deaf viewers understood signed video 24% better with captions added ([Debevc et al., 2015](https://doi.org/10.1371/journal.pone.0127577)): signing and captions together beat either alone.

Human interpreters are the gold standard but are rare on everyday online video, so most videos a Deaf viewer watches have captions at best.

## Solution today

English is translated into ASL order with grammar rules on a Stanza parse, matched to ASL Signbank signs, and played by a 2D signer animated from those dictionary videos with MediaPipe. Words without a sign are fingerspelled.

- **Extension:** uses YouTube's own captions and signs them a minute at a time from where the viewer is, so a 2-hour video starts signing in about 1.3 s.
- **Coverage:** all 3,509 Signbank signs that have a video are pre-animated; 372 hand-reviewed synonyms extend them. 74% of the 2,000 most common English words get a sign, 40% of the 10,000 most common.
- **Constraints:** openly licensed sign sources only, non-commercial, and translation simplifies ASL grammar (no facial grammar or classifiers).

## Success metrics

The north star is whether Deaf viewers find it helps them follow a video; installs only matter if that is true.

| Metric | Today (measured) | Target |
| --- | --- | --- |
| Deaf testers who say it helped them follow a video | Not yet tested | 5 of 8 in the first round |
| Wrong-sign reports per 1,000 signs shown | Not yet tracked (no report button) | Falling release over release |
| Common words with a sign (2,000 most common) | 74% | 85% |
| Average lag behind speech (fast 30 s test video) | 1.13 s | Under 1 s |
| Wait before the first sign on a new video | About 1.3 s | Under 2 s |
| Weekly users still active after 4 weeks | No data yet (Chrome Web Store dashboard) | Measure first, then set |

Coverage, lag and wait time are guardrails: they can improve while usefulness doesn't.

## What to build next, and why

1. **"Report a wrong sign" in the popup and the player.** Accuracy is the biggest risk, and today a bad sign is invisible to me. Moves: wrong-sign reports.
2. **Test with Deaf viewers and ASL teachers.** Watch 8 people use it on videos they choose, and fix what they flag. Moves: the north star; it decides everything below.
3. **Fluent-signer review of the 100 most common unsigned words** (*even*, *current*). These need a judgment only an ASL user can make; their choices go into the reviewed list. Moves: coverage, 74% toward 85%.
4. **A welcome page after install.** It shows how to turn on captions and where the signer appears, so first use doesn't fail silently. Moves: 4-week retention.
5. **Better ASL grammar** (topic first, time words first), checked by the same reviewers. Moves: helpfulness, once the basics are trusted.

Not next: more sign sources. The open ones add little (PopSign covers 28 missing, mostly toddler words), and the rest need permission.

## Risks and open questions

- **Trust:** signing avatars are controversial with many Deaf people, mainly when used in place of interpreters. Mitigation: present it as a layer next to captions, and let Deaf testers shape it.
- **Accuracy:** word-by-word signs lose ASL grammar, and synonyms were reviewed by a non-signer. Open question: how much wrongness do viewers tolerate before it hurts more than it helps?
- **Platform:** the extension depends on how YouTube's player loads captions, which YouTube can change at any time.
- **Licensing:** Signbank's licence is non-commercial, which rules out ever charging for it.
- **Cost:** one always-on server is about $25 a month, paid personally.
