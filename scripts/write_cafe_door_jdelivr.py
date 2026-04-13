"""
HEAD 커밋 SHA 를 jsDelivr 경로에 넣어 cafe-door.html 를 갱신합니다.
(cafe_door.bat 에서 git commit 직후·amend 전에 호출)

이유: ?v= 쿼리는 jsDelivr CDN 캐시 키에 안 쓰이므로 @main 만 쓰면 예전 PNG 가 뜰 수 있음.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_dashboard import write_cafe_door_html_jdelivr_commit_sha


if __name__ == "__main__":
    write_cafe_door_html_jdelivr_commit_sha()
