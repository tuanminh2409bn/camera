PYTHON ?= python3

.PHONY: help check test compile cli-help doctor smoke

help:
	@echo "DEV.ONE Secure Live - M0-M2 Local POC"
	@echo ""
	@echo "Các mục tiêu hỗ trợ:"
	@echo "  make check     - Kiểm tra cú pháp Python, CLI --help và chạy toàn bộ unit tests"
	@echo "  make test      - Chạy toàn bộ bộ kiểm thử unittest (stdlib)"
	@echo "  make compile   - Kiểm tra biên dịch bytecode cho scripts/ và tests/"
	@echo "  make doctor    - Kiểm tra công cụ máy trạm (JSON, không tự động cài đặt)"
	@echo "  make smoke     - Chạy kiểm thử khói MediaMTX native trên loopback (yêu cầu binary đã tải)"

compile:
	$(PYTHON) -m compileall -q scripts tests

cli-help:
	$(PYTHON) scripts/poc.py --help >/dev/null

test:
	$(PYTHON) -m unittest discover -s tests -v

check: compile cli-help test

doctor:
	$(PYTHON) scripts/poc.py doctor

smoke:
	$(PYTHON) scripts/poc.py smoke
