# A_22-rbs-standby-accessibility__20261017 — Active

- Scope: Reconstruct published standby geometry, unfolding and sliding as a versioned profile.
- Status: active
- Opened: 2026-10-17
- Updated: 2026-10-17
- Current State: Primary specification and structural optimization semantics are being checked; no model parameters are fitted and frozen Wave2 artifacts remain unchanged.
- Verification: Starting baseline 0a9fbd03326afc1baa918e85eb2dd7709f666b63 has 1,383 real-backend tests and four passing CI environments. New implementation checks are required below.
- Cleanup: Owner records final validation, distills reusable contracts, resolves/removes this ticket and its index row; broader #4 remains open where incomplete.
- Owner: Session A (baf5b738-1792172297), wave3/rbs-mechanisms.
- GitHub Issue: https://github.com/rohinshanker/regulatory-site-prediction-reconstruction/issues/22
- Parent: #4; integration #6.

Session A Wave3 scope under #4: reconstruct published standby-module geometry, selective unfolding and sliding as an explicitly versioned RBS profile.

Owner: Session A (baf5b738-1792172297). Shared baseline0a9fbd03326afc1baa918e85eb2dd7709f666b63; branch wave3/rbs-mechanisms. Only this session is launched; SessionB retains its own evidence/comparator scope.

Acceptance:
- Read primary2014 paper/supplement and relevant published source; pin equations, geometric definitions, parameters and optimization semantics before implementation.
- Implement a complete specified calculation rather than inserting only the distortion polynomial. Explicitly document unavoidable reconstruction choices and unsupported mechanisms.
- Preserve historical/footprint/context profiles and frozen learned artifacts. Expose selected module, coordinates, energy contributions and deterministic candidate choices only where semantics are established.
- Test structural geometry, selective unfolding/sliding, boundaries, strand conversions, errors, term-level ablations and independent analytic fixtures.
- Run real offline single/batch examples and development-only comparisons under frozen settings. Do not tune to consumed Wave2 final outcomes or imply biological superiority.
- Deliver reviewed commits, provenance, resource limits, model documentation and passing CI; leave broader kinetics/stacking gaps open.

Website collection/coins are deferred. No private outcomes, canonical main/cyano writes or main merge/public package. Before new credential/admin/macOS access, disclose exact action/resource/reason and wait for required authorization.
