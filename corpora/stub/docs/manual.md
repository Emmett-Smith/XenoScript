# Stub Manual

Overview of the stub corpus. It exists to unblock ingest, MCP server, and
harness development before the real PLINTH interpreter lands. See
`specs/02_BACKEND.md` #6.

## Getting Started

To verify a candidate program, run the stub verifier against it. The
background level concept in this stub language is modeled by the
`noise_floor` attribute, set inside a `platform` block.

### Attributes

- `noise_floor` — background level for a platform, in arbitrary units.
- `end_platform` — closes a `platform` block.

## Examples

A minimal program:

```
platform demo
  noise_floor 10
end_platform
```

Programs may inherit shared settings from another platform by name.
