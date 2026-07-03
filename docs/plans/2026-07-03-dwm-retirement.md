# DWM 표면 은퇴 — Depone을 "검증기 + 워크플로우 계약 설계" 제품 모양으로 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans.
> **브랜치 `dwm-retirement`에서 실행. main 직접 커밋 금지. push 금지(운영자 리뷰 후 머지).**
> 이 플랜의 keep/remove 경계는 2026-07-03 실측(참조 grep)으로 확정된 것이다 — 재분류하지 말고,
> 애매한 항목을 발견하면 **멈추고 보고**하라.

**Goal:** Depone repo의 ~80%를 차지하는 **DWM 개발 시절 표면**(운영·측정·벤치마크·도그푸드 도구와
그 개발일지·fixture)을 걷어내, repo를 **① 비실행 검증기(`depone/verify`,`agent_fabric`) +
② 워크플로우 계약 설계(`depone/compile`,`contract`, `SKILL.md`)** 라는 제품 모양으로 만든다.
기능(①②)은 하나도 잃지 않는다. 모든 제거물은 git 히스토리에 남는다(복구 가능).

## 확정 경계 (실측 근거 포함 — 2026-07-03)

**실측 사실:**
- `SKILL.md`는 scripts/를 하나도 호출 안 함 → ②는 패키지+문서로 자립.
- `tests/`(43개)는 scripts/를 하나도 참조 안 함 → 전 스크립트가 테스트 비커버.
- tests+패키지가 쓰는 fixtures = `fixtures/agent_fabric`, `fixtures/capabilities` **뿐**.
- tests+패키지가 쓰는 docs = 10경로 뿐(아래 KEEP 목록).
- `scripts/dwm.py doctor` = **docs/v* 개발일지의 존재를 검사하는 DWM 게이트**(제품 건강검진 아님).
- `scripts/check_contract.py`(~5k줄) = 스크립트 99개를 시퀀스 실행하는 **DWM 릴리스 계약 엔진**. CI 게이트.
- `scripts/execute_packet.py` 등은 subprocess 실행 → **비실행 불변식과 충돌하는 유산**.

### KEEP (건드리지 않음)
- `depone/` 패키지 전체(①+②), `tests/` 43개 전체, `pyproject.toml`, `LICENSE`, `AGENTS.md`, `CLAUDE.md`.
- `SKILL.md`, `templates/`, `references/` (워크플로우 설계 스킬 표면).
- `fixtures/agent_fabric/`, `fixtures/capabilities/`.
- docs 중 tests/패키지 참조 10경로: `docs/spec.md`, `docs/command-reference.md`, `docs/only.md`,
  `docs/depone-advance-one-step/`, `docs/depone-cloud-team-control.md`, `docs/depone-run-receipt-frontdoor/`,
  `docs/team-dry-run/`, `docs/worktree-lane-receipt/`, `docs/v107-agent-fabric-control-plane-spec.md`,
  `docs/v123-agent-fabric-controlled-capture-corpus-spec.md`. + `docs/plans/`(이 플랜 포함) +
  `docs/ops/` 있으면 유지 + release-readiness 플랜 유지.
- `assets/dwm-hero.svg` (README가 사용). `packaging/depone-agent-operating-contract.json`.
- `.github/workflows/ci.yml`의 **unit 매트릭스 잡과 witnessd 역방향 conformance 잡**.

### REMOVE (전부 실측상 무참조 또는 DWM 전용)
- `scripts/dwm.py` + `scripts/dwm_*.py` 76개 (doctor 포함 — docs/v* 존재검사 게이트).
- `scripts/` 중 DWM 운영·측정·실행 유산: benchmark/dogfood/frontier/control_deck/daily_operator/
  promotion/candidate 류 전부 + `orchestrate_workflow.py`, `run_workflow.py`, `dispatch_worker.py`,
  `execute_packet.py`, `evaluate_plan.py`, `compile_workflow.py`, `keelplane_*.py`,
  `seed_contract_workspace.py`, `v105_verify_wedge.py`, `v106_multi_wave.py`,
  `review_worker_result.py`, `run_worker_result.py`, `ingest_worker_review.py`,
  `resolve_human_gate.py`, `review_frontier_result.py`, `ingest_frontier_review.py`,
  `install_smoke.py`, `quick_validate_skill.py`, `run_tests.py` 등 — **원칙: KEEP에 명시 안 된
  scripts/는 제거 대상. 단 `check_contract.py`·`check_readme_quality.py`·`check_release_text.py`·
  `check_whitespace.py`는 아래 Task 3 처분을 따른다.**
- `fixtures/` 중 KEEP 2개 외 전부(v0.5~v106 백여 개 버전 디렉토리, keelplane-*, live-proof,
  contract-seed, verdict-integrity, research-codex 등).
- `docs/` 중 KEEP 외 전부(v0.5~v106 결정문/스펙/plan.json 개발일지 ~200파일 포함).
- `samples/`(check_contract 전용이었음), `assets/`의 dwm-hero.svg 외 전부(dogfood/benchmark svg·json),
  `packaging/`의 dwm-*.json, `agents/openai.yaml`(무참조 확인 후).

## Tasks

### Task 0: 브랜치 + 베이스라인
- [ ] `git checkout -b dwm-retirement`. 베이스라인 그린 기록:
  `uv run python3 -m unittest discover -s tests -p 'test_*.py'`(333 OK 예상) +
  witnessd 역방향(`cd /home/ubuntu/moonweave/witnessd && PYTHONPATH=/home/ubuntu/moonweave/depone uv run python3 scripts/revalidate_w1.py`).

### Task 1: REMOVE 세트 일괄 `git rm`
- [ ] 위 REMOVE 목록 실행. 각 대분류(scripts/fixtures/docs/samples/assets/packaging)별 커밋.
- [ ] 매 커밋 후 unit 333 OK 유지 확인(tests는 scripts 무참조라 깨지면 경계 오류 신호 → 멈추고 보고).

### Task 2: CI 재작성
- [ ] `ci.yml`에서 `check_contract --tier changed`와 `dwm.py doctor` 스텝 제거.
- [ ] 게이트 구성(전부 required): unit 3.10/3.12 매트릭스(기존) + witnessd 역방향 conformance(기존) +
  **새 슬림 게이트 1개**: `python3 -m depone.cli ... self-test`류 패키지 자체검증이 있으면 그것,
  없으면 `scripts/check_evidence_contract.py` 신규(±100줄: fixtures/agent_fabric·capabilities를
  실제 validator로 재검증 + KEEP docs 존재 확인 — 제거된 경로는 절대 참조 금지).
- [ ] 로컬에서 각 잡 커맨드 1회씩 그린 확인.

### Task 3: check_* 4종 처분
- [ ] `check_contract.py`: DWM 릴리스 계약 엔진이므로 **제거**하고 Task 2의 슬림 게이트로 대체.
  (witnessd 문서·moonweave Makefile `verify-depone`이 이를 참조 — **repo 밖이므로 건드리지 말고
  최종 보고에 "운영자 후속: Makefile verify-depone 갱신 + witnessd G3 문구" 명시.)
- [ ] `check_readme_quality.py`/`check_release_text.py`/`check_whitespace.py`: 내용 확인 후
  KEEP 표면만 검사하도록 남기거나(수정 최소), 제거된 경로를 검사하면 그 부분만 삭제.

### Task 4: 문서 정합
- [ ] README: 제거된 표면 언급(있다면) 정리, "historical DWM tooling" 문구를 "retired to git
  history (tag v0.1.0 preserves the full surface)"로 갱신. hero svg 유지.
- [ ] SKILL.md: 제거된 scripts 참조 없음(실측)이므로 내용 유지, DWM 별칭 문구는 그대로 둠(②의 이름).
- [ ] `docs/plans/README.md` 있으면 로드맵 갱신, 없으면 생략.

### Task 5: 최종 검증 + 정직한 커밋 메시지
- [ ] Final matrix(아래) 전부 그린 → 요약 커밋(제거 파일 수/남은 구조/게이트 변화 명시). push 금지.

## Final Validation Matrix
```bash
cd /home/ubuntu/moonweave/depone
uv run python3 -m unittest discover -s tests -p 'test_*.py'          # 333 OK (하나도 안 줄어야 함)
uv run python3 <새 슬림 게이트>                                        # PASS
grep -rn "dwm_\|check_contract\|samples/\|v105\|keelplane" .github/ scripts/ README.md SKILL.md \
  | grep -v "docs/plans/" || echo "removed-path refs clean"
cd /home/ubuntu/moonweave/witnessd && PYTHONPATH=/home/ubuntu/moonweave/depone uv run python3 scripts/revalidate_w1.py  # PASS (역방향 conformance)
```

**Explicit Non-Changes:** `depone/` 패키지 코드 수정 금지 / tests/ 수정 금지(깨지면 경계 오류 —
멈추고 보고) / 비실행 불변식·보안수리 불변 / main 커밋·push 금지 / witnessd repo·moonweave Makefile
수정 금지(후속 보고만) / 새 기능 금지.
