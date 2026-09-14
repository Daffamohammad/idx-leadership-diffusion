from __future__ import annotations

from idx_leadership.providers.official_market_context import (
    OJK_RDK_JUNE_2026_URL,
    build_official_market_context_payload,
)


MARKDOWN = """
# SP 131/DKPU/OJK/VII/2026 SIARAN PERS RDK JUNI 2026

Jakarta, 7 Juli 2026

<table>
<tr><th></th><th>30-Dec-2025</th><th>29-Mei-2026</th><th>30-Jun-2026</th></tr>
<tr><td>IHSG</td><td>8.646,94 22,13%</td><td>6.127,38 -29,14%</td><td>5.643,19 -34,74%</td></tr>
<tr><td>Saham (Rp T)</td><td>60,58</td><td>-53,97</td><td>-73,61</td></tr>
<tr><td>% Kepemilikan Lokal</td><td>—</td><td>—</td><td>59,41</td></tr>
<tr><td>Market Cap Saham (Rp T)</td><td>—</td><td>—</td><td>9.897</td></tr>
<tr><td>RNTH Saham (Rp T)</td><td>—</td><td>—</td><td>24,19</td></tr>
</table>

Pada Juni 2026, investor asing membukukan net sell sebesar Rp19,63 triliun.
"""


def test_ojk_parser_promotes_only_validated_market_context() -> None:
    payload = build_official_market_context_payload(
        MARKDOWN,
        source_url=OJK_RDK_JUNE_2026_URL,
        parsed_pages=(1, 2),
        retrieved_at="2026-09-13T00:00:00+00:00",
    )

    assert payload["status"] == "READY"
    assert payload["quantitative_use"] is True
    assert payload["period_end"] == "2026-06-30"
    assert payload["metrics"]["ihsg_close"] == 5643.19
    assert payload["metrics"]["equity_net_foreign_idr_trillion"] == -19.63
    assert payload["metrics"]["equity_net_foreign_direction"] == "NET_SELL"
    assert payload["metrics"]["market_cap_idr_trillion"] == 9897.0
    assert payload["context_compatibility"]["not_per_ticker"] is True
    assert payload["source"]["parser_agent"] == "LlamaCloud"
