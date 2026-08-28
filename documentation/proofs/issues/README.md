# Issue proof index

The panels in this directory were used to review font metadata, shaping, and
outline warnings. Most corresponding issues are closed because automated
checks now enforce the accepted result. Issue #24 remains open pending external
vendor-ID registration.

| Issue | Proof | Outcome |
| --- | --- | --- |
| [#20](https://github.com/NamcheAI/namche-fonts/issues/20) | [`issue-20-name-length.png`](issue-20-name-length.png) | Retained compatible static and variable names. |
| [#21](https://github.com/NamcheAI/namche-fonts/issues/21) | [`issue-21-language-shaping.png`](issue-21-language-shaping.png) | Defined the language-shaping contract and blocking checks. |
| [#22](https://github.com/NamcheAI/namche-fonts/issues/22) | [`issue-22-variable-interpolation.png`](issue-22-variable-interpolation.png) | Accepted the reviewed Sans variable interpolation baseline. |
| [#23](https://github.com/NamcheAI/namche-fonts/issues/23) | [`issue-23-outline-metrics.png`](issue-23-outline-metrics.png), [`issue-23-outline-heuristics.png`](issue-23-outline-heuristics.png) | Classified intentional outline and metric warnings. |
| [#24](https://github.com/NamcheAI/namche-fonts/issues/24) | [`issue-24-vendor-id.png`](issue-24-vendor-id.png) | Records the unregistered `NMCH` vendor ID; registration is still open. |
| [#25](https://github.com/NamcheAI/namche-fonts/issues/25) | [`issue-25-pixel-metadata.png`](issue-25-pixel-metadata.png) | Restored Pixel language and vendor metadata. |
| [#32](https://github.com/NamcheAI/namche-fonts/issues/32) | [`issue-32-pixel-separators.png`](issue-32-pixel-separators.png) | Restored the Pixel separator glyph exports. |
| [#33](https://github.com/NamcheAI/namche-fonts/issues/33) | [`issue-33-mono-hmetrics.png`](issue-33-mono-hmetrics.png) | Documented the minimum safe Mono horizontal-metric layout. |
| [#34](https://github.com/NamcheAI/namche-fonts/issues/34) | [`issue-34-pixel-rupee.png`](issue-34-pixel-rupee.png) | Approved the Pixel rupee construction. |
| [#35](https://github.com/NamcheAI/namche-fonts/issues/35) | [`issue-35-wws-metadata.png`](issue-35-wws-metadata.png) | Normalized family-specific WWS metadata. |
| [#36](https://github.com/NamcheAI/namche-fonts/issues/36) | [`issue-36-pixel-shaping.png`](issue-36-pixel-shaping.png) | Completed Pixel dotted-circle and soft-dotted shaping. |
| [#37](https://github.com/NamcheAI/namche-fonts/issues/37) | [`issue-37-pixel-ligature-carets.png`](issue-37-pixel-ligature-carets.png) | Preserved Pixel ligature caret positions. |

Regenerate all panels with:

```sh
venv/bin/python scripts/render_issue_proofs.py
```

The renderer depends on system text-rendering libraries and a reference font,
so visual output can differ slightly between platforms. Review changes rather
than treating byte identity as an automated test requirement.
