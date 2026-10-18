# Operon and Riboswitch source admission

- Purpose: Distinguish reusable open components from incomplete inference paths.
- Scope: Bounded Wave 5 source recovery for #35; no new calculator runtime or fitting.
- Last verified: 2026-10-18

No complete standalone current Operon or Riboswitch inference engine was established
in the inspected sources. The [source manifest](../../benchmarks/other-calculators/source-manifest.json)
pins repository trees, files, articles and supplements; missing components below
are implementation gates, not proof that code cannot exist elsewhere. The
inspected current SalisLabCode head remains
`46da9132740bce30bccd107f02808adf2215e2f0`. iDOG remains pinned at
`9d71187f0b2eb27ee681918927e12850470a0688`.

## Operon components

The [official contract](https://docs.salislab.net/design-genetic-systems/models-and-design-algorithms/operon-calculator)
takes a supplied promoter, 1–10 RBS/CDS pairs, terminator and host. It describes
initiation, elongation, stability, internal regulatory elements and annotated
export. That supplied-construct service is not evidence of a native genomic
operon-discovery algorithm. Adjacent CDSs cannot silently become a transcript.

| Component | Reusable evidence | Missing deployment requirement |
| --- | --- | --- |
| Translation initiation | Existing historical/footprint/context/standby RBS profiles, explicit RNAstructure backend and notices. | Coupled downstream initiation, drafting, kinetic and production-version equivalence remain separate. |
| Internal promoters | Admitted GPL-3.0-or-later Promoter source, 343 coefficients and executed synthetic fixtures. | A's runtime/source-parity acceptance and explicit context/calibration contract. |
| mRNA stability | MIT `mRNA_Stability_Calculator/ModelTrainingTesting.py`, hyperparameters and precomputed train/test features. | Complete sequence featurizer, frozen six-model artifacts, categorical feature/order contract and reproducible dependency lock. |
| Elongation, pausing, RNase protection | Official interface and cited study descriptions. | Executable integrated equations, host-specific parameters and independent fixtures. |
| Termination and genetic instability | Documented outputs and benchmark/parts leads. | Admitted inference source/weights, applicable conditions and false-positive validation. |
| Operon integration | Explicit supplied part order can be preserved without biological inference. | Verified transcript boundaries, isoforms, coupling semantics and joint resource/failure behavior. |

The iDOG `plot_operon.py` is visualization code. The inspected tree provides
`operon_design` and `web_operon_design` only as CPython 3.7 bytecode. Its MIT
notice does not turn those files into available maintainable source. The
Salis model-test wrapper imports `DNAc` and named RBS implementations absent from
that directory; a test harness is not their implementation.

## What the public stability package executes

[Cetnar et al. 2024](https://doi.org/10.1038/s41467-024-54059-7), Methods “Data
analysis and model development,” identifies LightGBM 3.3.2 and natural-log
RNA/DNA targets. The earlier Results model-development section describes five
predicted isoforms, Promoter v1.0, RBS v2.1 and ViennaRNA 2.4.11 feature generation.
The repository Dockerfile instead downloads ViennaRNA 2.5.0 and installs
unversioned packages. It is a historical environment recipe, not a release lock.

The script reads precomputed feature CSVs, trains five time-point regressors and
one decay-rate regressor, and writes fitted models. It does not implement the
sequence-to-feature step. No fitted model files occur in the inspected directory.
The exact train/test CSV members contain 36,219 and 9,064 data rows, respectively,
with 513 header fields. No model fitting or outcome metrics were run here.

An isolated [component smoke](../../benchmarks/other-calculators/stability-feature-smoke.json)
executed only the inspected original AST nodes `NUM_TOP_ISOFORMS` and
`returnKeepColumns`, without imports, training main or outcome loading. It
returned 460 unique time-point feature names and 465 decay feature names;
the latter adds five predicted time-point levels. This verifies a feature-schema
component only. The paper's stated 496-feature count is a different count and
must be reconciled before claiming feature parity. The CSV's full 513-column
header includes metadata/outcomes and must not become an inference feature list.
The training code filters the CSV columns by membership in this list, retaining
CSV order. The list hash alone therefore does not establish fitted-model feature
order; preserve both the CSV schema and model artifact metadata.

The MIT grant preserves the 2023–2024 Cetnar/Hossain/Salis notice. Source article
CC-BY-4.0 and repository component terms are recorded separately; no upstream
measurement tables or code are redistributed here. Required imports are NumPy,
pandas, matplotlib, LightGBM and scikit-learn, with openpyxl for Excel ingestion.
The README/Dockerfile also install packages unused by the inspected script;
those are not justified required dependencies. Existing ViennaRNA restrictions
remain incompatible with the project's required open dependency path. Replacing
its structural/G-quadruplex features with RNAstructure is a model change requiring
new feature/parameter validation, not a transparent backend substitution.

The source splits variants within design groups into training/test populations.
It therefore does not establish generalization to unseen design families or
native cyanobacterial transcripts. Six fitted artifacts plus training rights,
feature provenance and a genuinely independent challenge are separate gates.

## Riboswitch inference boundary

[Espah Borujeni et al. 2015](https://doi.org/10.1093/nar/gkv1289) and its supplement
provide a specified-aptamer model: unconstrained and ligand-constrained RNA/RBS
states, maximum activation, concentration-limited occupancy and a metastability
correction. Required inputs include transcript/CDS context, exact aptamer span,
ligand-bound structure, binding energy or explicitly standardized dissociation
constant, temperature, concentrations and volume assumptions. These inputs do
not identify a native aptamer or establish its binding structure.

The supplement's equations S4–S19 (PDF pages 23–27) separate these quantities.
The volume-based equilibrium model, S20–S26 (pages 28–29), conserves mRNA and
ligand and uses volume-adjusted partition functions. A generic Hill equation is
not an equivalent replacement. Its assumed intracellular concentrations and
relative molecular volumes (pages 33–34) are estimates, not universal host
measurements. Preserve the distinction between nominal model beta and a slope
fitted to reporter measurements.

[Five independent scalar fixtures](../../benchmarks/other-calculators/riboswitch-scalar-fixtures.json)
use explicit synthetic beta 0.45 and supplied bound fractions. They check equal
ON/OFF states, zero/all/quarter occupancy and positive switching cost with
50-digit Decimal arithmetic. They are algebra fixtures, not a recovered folding
engine, occupancy solver or experimental prediction. The positive-cost correction
is conditional; applying it to every stable switch changes the published model.

Pseudoknots need additional source admission. Supplement pages 31–32 specify a
1.3 kcal/mol assembly term, coaxial stacking and entropy terms attributed to
Cao/Chen and DotKnot, and canonical-stem energies calculated using ViennaRNA
1.8.5. The [DotKnot author site](https://dotknot.csse.uwa.edu.au/references.html)
links version 1.3.2 and its parameter references; the archive returned HTTP 403
to this retrieval. Its exact source/parameter licence and bytes were therefore
not verified or bypassed. Required general pseudoknot support cannot be claimed
from a canonical secondary-structure backend or those references alone.

The 2015 paper/supplement grant is CC-BY-NC-4.0. It is not a permissive software
grant or authority to bundle those data into the required open runtime. Scalar
relationships are independently expressed here; original supplements stay in
the external evidence cache. The complete published constrained-RBS/ligand-state inference path remains
unrecovered. The separately admitted [canonical constrained-folding component](riboswitch-constrained-reference.md)
now supplies exact nested pair/unpaired demands, pinned RNAstructure 6.6
identities, nine executed synthetic cases and offline output re-auditing. It is
a different backend from the published ViennaRNA configurations, and does not
supply constrained intermolecular RBS cofolding or ligand occupancy.

## Protein-binding extension and benchmark exposure

[The 2023 study](https://doi.org/10.1038/s41467-023-38098-0) supplies a CC-BY-4.0
Source Data workbook (third-party exceptions retained), with sequences,
calculations, measurements and statistical tests. The retrieved workbook SHA256
is `eed842253c93d2bbe10f9b3de98a616ee0ad29cac78862bc603e05d2ede0c892`.
Its Methods describe ViennaRNA v2.5/Turner 2004/no dangling energies for aptamer
constraints, and Riboswitch/RBS v2.1 inference under Python 2.7/3.7.7.
This is environment evidence, not a recovered complete open implementation.

Results “Accuracy analysis and improvement by modifying aptamer structural
constraints” selects aptamer subconstraints for best overall agreement across
measured switches. Its improved correlation is exposed constraint optimization,
not an untouched final evaluation. Preserve no-aptamer normalization, separate
cell-free/protein-dose conditions and shared aptamer families. The observed
steric inhibition is not supplied as a complete general steric-hindrance model.

## Ordered implementation contract

1. Continue RBS release preparation and owner-authorized isolated Promoter
   implementation under their separate publication and evaluation gates. Preserve transcript/part organization and null
   outputs for unsupported submodels in any future supplied-operon contract.
2. Recover or explicitly reconstruct stability featurization, categorical schema
   and all six artifact identities before promising sequence-to-decay inference.
   Independently verify admitted feature fixtures and family-separated evaluation;
   do not train this wave or tune an artifact against its reported test set.
3. Admit each elongation, termination, protection/coupling and instability
   submodel with its own parameter/dependency pins. Integration must report which
   components ran; an annotated parts diagram is not a completed Operon Calculator.
4. Implement Riboswitch scalar/occupancy relationships only with explicit input
   units, conservation and limiting-case tests; use the admitted canonical constrained
   folding fixtures without implying published-backend parity. General pseudoknot and protein-steric
   support remain separate gates with explicit unsupported results.
5. Freeze supplied-aptamer assay panels by aptamer/construct family and study.
   Keep source-equation, hosted-reference and experiment comparisons separate.
   Native cyanobacterial aptamer discovery needs independent annotations and
   experimental evidence; this conditional calculator cannot supply that truth.

This admission package completes a bounded search and records actionable gaps.
It does not close the broader source, Operon, Riboswitch or suite implementation
parents. No website job, credential, package publication or cyano change is
required to reproduce the public-source evidence above.

## Reproduction

Retrieve the exact raw `ModelTrainingTesting.py` URL in the manifest into an
external cache as `stability-ModelTrainingTesting.py`. Do not run its top-level
module: that path imports the training stack and executes fitting. The following
standard-library smoke verifies the admitted source bytes before executing only
the two inspected schema nodes. It reads no measurements and installs nothing.
Pass the external cache path as the argument.

```sh
python3 - /path/to/stability-ModelTrainingTesting.py <<'PY'
import ast
import hashlib
from pathlib import Path
import sys

source = Path(sys.argv[1]).read_bytes()
assert hashlib.sha256(source).hexdigest() == (
    "de015f8aef21aeb584c3a15a04131fe6f46060ba679ff17b5f4dd923e0f42bf0"
)
tree = ast.parse(source)
nodes = [node for node in tree.body if (
    isinstance(node, ast.Assign)
    and any(isinstance(target, ast.Name) and target.id == "NUM_TOP_ISOFORMS"
            for target in node.targets)
) or (isinstance(node, ast.FunctionDef) and node.name == "returnKeepColumns")]
assert len(nodes) == 2
namespace = {}
exec(compile(ast.Module(body=nodes, type_ignores=[]), sys.argv[1], "exec"), namespace)
for decay in (False, True):
    columns = namespace["returnKeepColumns"](decay)
    digest = hashlib.sha256(("\n".join(columns) + "\n").encode()).hexdigest()
    print(decay, len(columns), len(set(columns)), digest)
PY
```

The expected counts and ordered LF-terminated feature-list hashes are in the
smoke receipt. The five scalar fixtures are checked by independently expressed
floating-point arithmetic:

```sh
python3 -m unittest discover -s tests/benchmarks -p test_other_calculator_fixtures.py
```

Acquisition archive hashes identify downloaded bytes; Europe PMC can regenerate
ZIP containers. Verify the pinned member hashes when a container changes, rather
than treating a changed ZIP hash as changed scientific content. Original article
licence elements were inspected separately for all three papers; supplement
equations S19/S20/S27 were checked against rendered PDF pages 27/29/31.
