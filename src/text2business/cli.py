from __future__ import annotations

import json
from datetime import datetime

from text2business.models import IncomingRequest
from text2business.workflow import run_case


DEMO_REQUEST = IncomingRequest(
    channel="email",
    sender='Андрей, «СеверФуд»',
    received_at=datetime.fromisoformat("2026-08-13T16:40:00+03:00"),
    text=(
        "СеверФуд, склад на Дмитровском шоссе, 100. "
        "ХУ-18 не запускается после перезагрузки. "
        "Продукцию пока перенесли в соседнюю камеру. "
        "Нужен выезд специалиста."
    ),
)


def main() -> None:
    result = run_case(DEMO_REQUEST)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

