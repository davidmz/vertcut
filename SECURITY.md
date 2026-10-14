# Security

## What Vertcut exposes

Vertcut runs a small web server for its screen. It listens **only on
`127.0.0.1`** — your own computer, not your network. Every start makes a
new random pass, and the server answers only requests that carry it
(in the address the browser opens, or in a header). It also checks that
requests come from its own page (the `Host` and `Origin` headers), so
another website open in the same browser can't drive it.

Without the pass it answers exactly one thing: a health check that says
whether it's running and at which address, pass included, so that a
second click on the Vertcut icon can open the same tab. Only programs
on your own computer can read that answer — the same programs could
read Vertcut's settings folder anyway. Other websites can't: requests
from them are refused before they get there.

Your AI API key, if you entered one, is stored in `~/.vertcut/` on your
computer and sent only to the AI provider you chose. On macOS and Linux
the file is readable only by you. On Windows it currently has the
default permissions of your user folder.

## Reporting a problem

If you found a way around any of this, or another security problem:

- **Not sensitive** (it can't be used against people who have Vertcut
  right now): open an [issue](https://github.com/eduard1414ed/vertcut/issues).
- **Sensitive:** please don't post the details publicly. Use
  [Report a vulnerability](https://github.com/eduard1414ed/vertcut/security/advisories/new)
  on GitHub, which reaches only the maintainer. If that's not available,
  open an issue that says only "security problem, please contact me",
  without details.

Vertcut is maintained by one person in their free time. You'll get an
answer, but maybe not the same day.
