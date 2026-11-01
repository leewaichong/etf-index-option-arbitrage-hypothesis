# Source provenance inventory

Original source checkout HEAD: `a922aa7a79c91d748d26048ecef694e9a93c45f1`.

The overnight-hedge export was evaluated from a separate clean source checkout
at `db5d980c7abc344af02e8ae98fc426da92df433e` on 2026-10-29. That evaluated
source SHA is distinct from the original checkout HEAD above. The two added
files below were copied byte-for-byte from that checkout.

Hashes compare each allowlisted original source file with its public export. The inventory includes twelve source files, eleven test files and four runners. It lists no private file paths, row selections, run artifacts or licensed inputs.

| File | Original SHA-256 | Exported SHA-256 |
|---|---|---|
| `src/spyspx/__init__.py` | `38424c2038799bfe9af53c1085369a7e91495c9525131ff0e879d2e39609f6c0` | `38424c2038799bfe9af53c1085369a7e91495c9525131ff0e879d2e39609f6c0` |
| `src/spyspx/expiry_payoff.py` | `c7eaf0c90fd5e029dac3012630af88646c0c8329697279a198ffd4842a8fbb48` | `c7eaf0c90fd5e029dac3012630af88646c0c8329697279a198ffd4842a8fbb48` |
| `src/spyspx/expiry_payoff_source.py` | `00a5f753b76cbfded7a9147906db593cf2477ed0abb4bf45cf9cd0b4635f1f26` | `00a5f753b76cbfded7a9147906db593cf2477ed0abb4bf45cf9cd0b4635f1f26` |
| `src/spyspx/expiry_extension.py` | `6a5964a78334cbe2d8fa3f1285221223eb609daeb39061036e62a022f9c481d0` | `6a5964a78334cbe2d8fa3f1285221223eb609daeb39061036e62a022f9c481d0` |
| `src/spyspx/expiry_replication.py` | `dc76bb59f9a85cb097463ddd836942d100a61039ca9742bd1738d27437a16327` | `dc76bb59f9a85cb097463ddd836942d100a61039ca9742bd1738d27437a16327` |
| `src/spyspx/expiry_attribution.py` | `fcdfcf3d306742684444002c64d65ff5c470878ee1622446d3a51ec73f632ebd` | `fcdfcf3d306742684444002c64d65ff5c470878ee1622446d3a51ec73f632ebd` |
| `src/spyspx/optionmetrics_admission.py` | `c9ab3d063535b588ab0f9d42f2d8549e6f6d711942a6aff2cc2cca9f8439a506` | `c9ab3d063535b588ab0f9d42f2d8549e6f6d711942a6aff2cc2cca9f8439a506` |
| `src/spyspx/optionmetrics_normalizer.py` | `045971a5b41c83d311b40f6733a7c20578b5e326ada4fdbc0417a9e1506a8130` | `045971a5b41c83d311b40f6733a7c20578b5e326ada4fdbc0417a9e1506a8130` |
| `src/spyspx/optionmetrics_replication.py` | `c010d765e58d0130b3f61b4253a8e1e08ca068b5e7a920c69e424e12952e59b8` | `c010d765e58d0130b3f61b4253a8e1e08ca068b5e7a920c69e424e12952e59b8` |
| `src/spyspx/optionmetrics_timing.py` | `e6b88d5694cabe3ebaa7e163537d6325c09304cdd2df2f48fb0581a89a57993b` | `e6b88d5694cabe3ebaa7e163537d6325c09304cdd2df2f48fb0581a89a57993b` |
| `src/spyspx/optionmetrics_stockrefs.py` | `b65149e8fcd555607933fee88a019aa8b3a4c57ff1c1891ec67f3cd5286cdc2e` | `ba93a56b84281dbe0ff6d4e6b4fae6dd7c8c95859d18aada6384e0617cf0a27d` |
| `tests/test_expiry_attribution.py` | `6fc9932852809fa702cba0099b408fada06ab1987d82758240152fd1ba5f8c18` | `dba052172c28dbef2998ce4c0a6c651c197a5d5b14a0fc342ac7105a698f6047` |
| `tests/test_expiry_extension.py` | `c58acb84616aa29e7ac9dd17ef571ae433d359963d34c199b0b18109f7bff7d7` | `c58acb84616aa29e7ac9dd17ef571ae433d359963d34c199b0b18109f7bff7d7` |
| `tests/test_expiry_payoff.py` | `0f4c12d6079229edad896793f685b6d559d54896dc92944e6eb343cb02899aa5` | `0f4c12d6079229edad896793f685b6d559d54896dc92944e6eb343cb02899aa5` |
| `tests/test_expiry_payoff_cli.py` | `16f46ac07712708f48489f8e9a8781430d2ded70d097b2b669cd495e42000f72` | `16f46ac07712708f48489f8e9a8781430d2ded70d097b2b669cd495e42000f72` |
| `tests/test_expiry_replication.py` | `c1258d3f589580798a0a427d00bfb2f9fa9756e52e10b23d2dced226469f45bd` | `c1258d3f589580798a0a427d00bfb2f9fa9756e52e10b23d2dced226469f45bd` |
| `tests/test_optionmetrics_admission.py` | `16aa332fe2af49b1655457c4b1a37e723f727df2d6f6dab3180bcd5daead73f7` | `16aa332fe2af49b1655457c4b1a37e723f727df2d6f6dab3180bcd5daead73f7` |
| `tests/test_optionmetrics_normalizer.py` | `54edfebced25cbba3fea012c71c7aa37848308baf3e29283f495dba7e055f26c` | `54edfebced25cbba3fea012c71c7aa37848308baf3e29283f495dba7e055f26c` |
| `tests/test_optionmetrics_replication.py` | `0a68f0695399ce95667daf3edafd6f059ab874945266408bf8d2a791ecd4b6a8` | `0a68f0695399ce95667daf3edafd6f059ab874945266408bf8d2a791ecd4b6a8` |
| `tests/test_optionmetrics_stockrefs.py` | `b54cbdbfff998bac688fff3ce599c746005e48ad3cc6ccc579f47ad6a49bf15f` | `b54cbdbfff998bac688fff3ce599c746005e48ad3cc6ccc579f47ad6a49bf15f` |
| `tests/test_optionmetrics_timing.py` | `183fd8ccde20f19bcdba3559414e78f0e9a13ef29107eaf86623a4da141c1c82` | `da6034eb57522b1686024a7749b1dd109b842582a47e9ffe0b7aa7e784a8a90e` |
| `scripts/expiry_payoff.py` | `4ee25187500a5cd7c1cf82b164af41fc05ce7b6830c7b9850a8e2369ffe983ce` | `4ee25187500a5cd7c1cf82b164af41fc05ce7b6830c7b9850a8e2369ffe983ce` |
| `scripts/expiry_extension.py` | `dd28a5dd65eb35df924e5d0ca9052a2936afc0df35c98a810d758cc6e7a0d9af` | `dd28a5dd65eb35df924e5d0ca9052a2936afc0df35c98a810d758cc6e7a0d9af` |
| `scripts/expiry_replication.py` | `e2a3dd803e818057bbbce5c919e60861e074821518490f0d0204df89842ca5e3` | `46ddc5f2dd7bba78e309993cea592115e3d3bf62aa788902256e49b8ad5acdb0` |
| `scripts/expiry_attribution.py` | `3e0858f960f926adbb6ca3aebe77fa520e8a58e4c13c12707d9cdf4982bf3ccd` | `3e0858f960f926adbb6ca3aebe77fa520e8a58e4c13c12707d9cdf4982bf3ccd` |
| `src/spyspx/overnight_hedge.py` | `6cca6772325e7d55c8a85ef6a444681d2a54175e9ddfb10949dfdae6748337f3` | `6cca6772325e7d55c8a85ef6a444681d2a54175e9ddfb10949dfdae6748337f3` |
| `tests/test_overnight_hedge.py` | `c98e909bb4ee0534ce127cc56d40a2e720bcfcc93630d24af4159a305fc4850b` | `c98e909bb4ee0534ce127cc56d40a2e720bcfcc93630d24af4159a305fc4850b` |

## 2023 morning-hedge export

The public checkout HEAD is `9208a575df30da1bcc9bd28525ed45b06e4644aa`.
The 2023 adapter was evaluated from a different clean source checkout at
`64e72887b782fdf838257a09877ffb817dfbfbdf`. The source module matches its
evaluated bytes exactly. The
public test file has eight fixture-aware skip markers so its calendar and
manifest tests run when the private frozen fixtures are present; test assertions
are unchanged.

| File | Evaluated SHA-256 | Public SHA-256 |
|---|---|---|
| `src/spyspx/morning_hedge_2023.py` | `02cd50de29e5c843a2bbace14ce1825d6027ea2268eec105878396a2030b8a13` | `02cd50de29e5c843a2bbace14ce1825d6027ea2268eec105878396a2030b8a13` |
| `tests/test_morning_hedge_2023.py` before fixture-aware skip markers | `9107f63b64d4affb079d863cd68f76dbf4e0982d5e63359ce636188a85bacb48` | `6afafbf4d332e0f1b0cdf0965eecc87777307489cb503d69c5cd48691dea2a6d` |

The public historical rerun remains **NOT RUN**. The evaluated run used licensed
inputs and private frozen controls that are not included in this repository.

## Morning-hedge attribution export

The attribution evaluation used clean Git SHA
`9a7c219c6ef886929621fc3863cf51dca660a6d6`. The exported production module is
byte-identical to the evaluated module. The public test copy was adapted only in
the portable authorization test, which now validates in-memory protocol cases
instead of reading an ignored planning file.

| File | Evaluated SHA-256 | Public SHA-256 |
|---|---|---|
| `src/spyspx/morning_hedge_attribution.py` | `36ec51840e6a5ff77ca9403e6557199963bd6b6ec40077bbdcfa965808e129cb` | `36ec51840e6a5ff77ca9403e6557199963bd6b6ec40077bbdcfa965808e129cb` |
| `tests/test_morning_hedge_attribution.py` before portable authorization test | `af66d70333e5a3362f2b941283b3a2eed47b752310f9367fcc2679c48cb42e45` | `07146b400d78fe52a63bd8e476596ac49310567c09bf6703182463a5ceb40ebd` |

The public aggregate-only attribution summary has SHA-256
`ac33f98ce67b3f955fb6d2a63958fa1bcc5404ccfed2a471f5271bddf13e06db`. It
contains selected year-level tables and provenance identifiers, not private
trade rows or bootstrap draw arrays.

## Archived eight-page morning-hedge assessment

The reviewed eight-page assessment is preserved at
`reports/expiry-payoff/archive/morning-hedge-assessment-before-2024-comparison-20261030.pdf`
and the matching `.md` file. Its PDF SHA-256 is
`00758646ff7464ea510ab15c731f1f861520b6e8df60818fdce61f66ee3a6e68`; its
Markdown SHA-256 is
`a6ec9bfe318add9eefd87a37548e464beaf5dd89e9f34eb520a9e8fd6875f9c8`.
The earlier five-page version is preserved in
`reports/expiry-payoff/archive/morning-hedge-assessment-before-year-attribution-20261030.pdf`
and the corresponding `.md` file. Its archived PDF SHA-256 is
`2c3640bd158d5a6e86a445b5a327d9f354bd55fa40b859679190475805e41663`; its
archived Markdown SHA-256 is
`a9115a0349ab23f64ea32b1dde5339461b4742aeb54ffcbbabdad23aaaeb403b`.

## Three-year morning-hedge comparison

The public aggregate summary contains year cohorts, monthly aggregates, tail
removals, within-year confidence intervals, sensitivities and provenance hashes.
It omits command arguments that contain private absolute paths. The source
aggregate SHA-256 is
`aa4887efd7e11f2478cb361b5ec0af37c863c324581cee2c4e3f17ff1f58aff6`; the
public sanitized summary SHA-256 is
`355b7823fdb3e4cf5a1868abdfcd2e00d842238e2d1e07a0254122a67b6468b4`.

The builder ran from clean Git SHA `1ce2763318f930f793da29293f6b5df482ef3b42`
with code SHA-256
`c154660c93f5faa269742428d516cf0cd544232147eaa7a7af390a4363ce1047`. The
2023 evaluator Git SHA was `64e72887b782fdf838257a09877ffb817dfbfbdf`; the
2024/2025 evaluator Git SHA was `44ed294deddb85df594ad1e1c8a5a91bb22d08d7`.
The run receipt SHA-256 is
`f2bc5ec4f7882e0c4339384d82ed4943852a5ee4d8be2e481a3167df032b8004`; the
approved findings SHA-256 is
`5e29acbac470ac4ba2d18010d76ba609b8398c7c421dd582e4455f09dfd075c8`.

Independent validation passed 2,397 checks with zero mismatches and maximum
error `1.78261e-10` at tolerance `1e-7`. Validation record SHA-256 is
`4d1b55c5c2010a066a86bec07fa14402033145ff36c80bbfeba00a5c0c753876`; its
execution record SHA-256 is
`bcff7d85aeb930e872d77c64f54ba8d0ee4f2b135da22ca3041ad4d2f8bd3d0e`.
The 2024 raw rerun check also passed 2,361,458 checks with zero mismatches; the
available record identifier begins `b940`.

The final five-page report PDF SHA-256 is
`3fb35898dccf8153a4bbda99063563c8bd5be429f44f1a210be766867bb822b7`; its
Markdown SHA-256 is
`cb4b32d31672bed36e7b97c751b73aba0d8fc9ad4436e4ad4e33c1c243bd312f`.
The clean render used Git SHA `c2bb0fb52e3a281518d829bebdc9a6d346c92349`;
the external render receipt SHA-256 is
`bce5520a753c5e8e01d39624ca8c0c51b76b0bd8ef693b6c4b0d8a61512d6eb7`.

The report renderer was copied byte-for-byte to
`artifacts/build_morning_three_year_report.py`, SHA-256
`4e7a946289b3164a3bbb320db2db87fd5deaf12dee90c32197a4ce63c8e74406`. The
comparison builder and pipeline test were withheld because they contain private
absolute paths. Their exact hashes are retained in the ignored local receipt.
The licensed historical inputs are not present in this checkout, so no public
raw-data evaluation was run.

## Publication-only edits

- `src/spyspx/optionmetrics_stockrefs.py` replaces machine-specific input and code roots with documented `SPYSPX_STOCKREFS_*` variables and ignored repository-relative defaults. Frozen hashes, accounting, selection and parity guards remain intact.
- `scripts/expiry_replication.py` replaces its machine-specific input default with `SPYSPX_2019_INPUT_ROOT` and an ignored repository-relative default.
- `tests/test_optionmetrics_timing.py` keeps all protocol, manifest and prior-version hash assertions. It skips this private-fixture integration check only when one or more of its three frozen control files are absent.
- `tests/test_expiry_attribution.py` creates its ignored `runs/` scratch parent before making the synthetic CLI sandbox, so the tests work in a fresh checkout without a global bootstrap.
- `src/spyspx/overnight_hedge.py` and `tests/test_overnight_hedge.py` were copied byte-for-byte from the clean evaluated source checkout at `db5d980c7abc344af02e8ae98fc426da92df433e`.
- All other allowlisted code, tests and runners match the source checkout byte-for-byte.
