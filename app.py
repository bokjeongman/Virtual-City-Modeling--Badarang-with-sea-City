"""실행: python app.py"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="가상 도시 / 공공서비스와 환경")
    parser.add_argument(
        "--smoke", action="store_true", help="화면 생성과 갱신을 확인한 뒤 종료합니다."
    )
    args = parser.parse_args()

    try:
        import tkinter
        from service_gui import launch
    except ImportError as error:
        print(f"실행에 필요한 모듈을 찾을 수 없습니다: {error}", file=sys.stderr)
        print(
            "폴더 전체를 압축 해제한 뒤 실행하세요. python -m tkinter로 Tkinter 설치를 확인할 수 있습니다.",
            file=sys.stderr,
        )
        return 1

    try:
        launch(smoke=args.smoke)
    except tkinter.TclError as error:
        print(f"GUI를 시작할 수 없습니다: {error}", file=sys.stderr)
        print(
            "화면이 있는 PC에서 실행하세요. Python 설치 프로그램에서 Tcl/Tk를 선택해 설치할 수 있습니다.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
