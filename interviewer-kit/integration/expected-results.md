# Integration exercise: expected results

Amounts are in minor units, with the formatted value the CLI prints in brackets.

| Merchant | Charges returned by `list_charges` | Currency | Gross | Fees | Refunds | Net | Succeeded charges | Payout |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `acct_tidewater` | 6 | usd | 37999 (379.99) | 1411 (14.11) | 2000 (20.00) | 34588 (345.88) | 4 | 34588 (345.88) |
| `acct_nimbus` | 57 | eur | 192154 (1,921.54) | 7129 (71.29) | 65196 (651.96) | 119829 (1,198.29) | 13 | 119829 (1,198.29) |
| `acct_nimbus` | 57 | usd | 839243 (8,392.43) | 32224 (322.24) | 112866 (1,128.66) | 694153 (6,941.53) | 33 | 694153 (6,941.53) |
| `acct_orchard` | 23 | eur | 4800 (48.00) | 234 (2.34) | 4800 (48.00) | -234 (-2.34) | 2 | none |
| `acct_orchard` | 23 | gbp | 96403 (964.03) | 3809 (38.09) | 7167 (71.67) | 85427 (854.27) | 12 | 85427 (854.27) |
| `acct_sprout` | 3 | eur | 6500 (65.00) | 277 (2.77) | 6400 (64.00) | -177 (-1.77) | 2 | none |
| `acct_breakeven` | 1 | usd | 1000 (10.00) | 59 (0.59) | 941 (9.41) | 0 (0.00) | 1 | none |
| `acct_ghost` | 0 | none | | | | | | none |

## Totals that common mistakes produce

For `acct_nimbus`, the merchant that exposes every mistake.

### eur

| Field | Correct | Wrong value | What produces it |
| --- | --- | --- | --- |
| fees | 7129 | 5901 | without the cross-border surcharge |
| fees | 7129 | 8784 | with the surcharge applied to every charge |
| fees | 7129 | 7127 | with 2.9% and 1.5% added before rounding (4.4% rounded once) |
| fees | 7129 | 7127 | with banker's rounding (round half to even) |
| fees | 7129 | 7115 | with percentages truncated instead of rounded |
| fees | 7129 | 10237 | with fees charged on pending and failed charges too |
| fees | 7129 | 9040 | with fees charged on pending charges too |
| gross | 192154 | 287201 | with pending and failed charges included |
| gross | 192154 | 247652 | with pending charges included |
| gross | 192154 | 17299 | from the first page of charges only (10 per page) |
| gross | 192154 | 63698 | from the first page of charges only (20 per page) |
| refunds | 65196 | 65946 | with failed refunds included |
| refunds | 65196 | 30146 | from the first page of refunds only (10 per page) |
| refunds | 65196 | 36146 | from the first page of refunds only (20 per page) |
| refunds | 65196 | 0 | with no refunds subtracted |
| charge_count | 13 | 17 | with pending and failed charges included |
| charge_count | 13 | 15 | with pending charges included |

### usd

| Field | Correct | Wrong value | What produces it |
| --- | --- | --- | --- |
| fees | 32224 | 25330 | without the cross-border surcharge |
| fees | 32224 | 37921 | with the surcharge applied to every charge |
| fees | 32224 | 32222 | with 2.9% and 1.5% added before rounding (4.4% rounded once) |
| fees | 32224 | 32219 | with banker's rounding (round half to even) |
| fees | 32224 | 32196 | with percentages truncated instead of rounded |
| fees | 32224 | 37971 | with fees charged on pending and failed charges too |
| fees | 32224 | 34656 | with fees charged on pending charges too |
| gross | 839243 | 986708 | with pending and failed charges included |
| gross | 839243 | 892491 | with pending charges included |
| gross | 839243 | 126097 | from the first page of charges only (10 per page) |
| gross | 839243 | 209073 | from the first page of charges only (20 per page) |
| refunds | 112866 | 146571 | with failed refunds included |
| refunds | 112866 | 35250 | from the first page of refunds only (10 per page) |
| refunds | 112866 | 102616 | from the first page of refunds only (20 per page) |
| refunds | 112866 | 0 | with no refunds subtracted |
| charge_count | 33 | 40 | with pending and failed charges included |
| charge_count | 33 | 36 | with pending charges included |
