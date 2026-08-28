# npm trusted publishing

The `release-npm` job in `.github/workflows/ci.yaml` is the only workflow
authorized to publish `@namche/namche-shadow`. It runs on GitHub-hosted Linux,
requests `id-token: write`, uses Node 22.22.3 and npm 11.19.0, and does not use
an `NPM_TOKEN`.

## Current configuration

The initial package bootstrap is complete. npm trusts the `release-npm` job in
`NamcheAI/namche-fonts/.github/workflows/ci.yaml` to publish this package.
Keep that repository, workflow filename, and npm package name synchronized.

The package should remain configured to require two-factor authentication and
disallow token publishing. The workflow uses short-lived OIDC credentials, so
it continues to publish without an npm automation token.

To restore the trusted-publisher configuration if it is removed, an owner of
the `namche` npm organization can run this with npm CLI 11.5.1 or newer:

```sh
npm trust github @namche/namche-shadow \
  --repo NamcheAI/namche-fonts \
  --file ci.yaml \
  --allow-publish \
  --yes
```

The workflow filename is only `ci.yaml`, not `.github/workflows/ci.yaml`; every
value is case-sensitive.

## Verification and recovery

After changing the workflow identity or npm publishing settings, verify one
OIDC release before revoking any temporary recovery credential. Do not add an
`NPM_TOKEN` secret to the workflow. If a release fails, check the repository,
workflow filename, environment, and package name configured on npmjs.com.

Trusted publishing automatically adds provenance for this public package from
this public repository; no `--provenance` flag or npm secret is required.
