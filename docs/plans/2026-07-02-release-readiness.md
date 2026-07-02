# Depone Release Readiness — CI + 정직한 README + v0.1.0 태그 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans.
> 이 웨이브는 **굳히기**다 — 새 검증 기능 추가 금지. witnessd가 v1.0.1(CI-green)에 도달했으니
> 그 검증기 짝인 Depone을 같은 릴리스 라인에 세운다. 대표작이 "실행기+독립 검증기 2제품"인데
> witnessd만 릴리스 품질이면 서사가 절뚝인다 — 이 비대칭을 닫는다.

**Goal:** (1) GitHub Actions CI(테스트 + 계약 + doctor), (2) 정직한 README(무엇을 검증하고 무엇을
안 하는지, 보안 수리 이력, 한계), (3) `v0.1.0` 태그. **아무 검증 로직도 바꾸지 않는다.**

## Context — Depone이 무엇인가 (README·CI가 정확히 반영해야 할 사실)

- **비실행(non-executing) 증거 검증기/공증 레이어.** 에이전트를 실행하지 않는다 — 다른 런타임
  (witnessd 등)이 방출한 서명 증거 바이트에서 A0/A1/A2 assurance를 **오프라인 재도출**만 한다.
  등급을 **올릴 수 없다**(verifier는 assurance 상향 불가). `depone/`은 SoT 계약(capture-manifest/
  runner-receipt/isolation/DSSE/team-ledger 스키마+에러코드)을 소유한다.
- **2제품 중 검증기 절반.** 실행기 = witnessd(별도 repo, github.com/Moonweave-Systems/witnessd, v1.0.1).
  둘의 유일 결합 = 증거 계약. moonweave 워크스페이스에서 co-dev하되 모노레포 아님.
- **보안 수리 이력(README에 정직히):** 2026-07-01 총리뷰에서 "서명 없는 JSON 하나로 A1/A2 등급 위조 가능"
  P0 결함이 적대적 검증으로 확증됨 → PR #62로 수리(evidence dir **밖**의 trusted-observer provenance +
  Ed25519 DSSE 요구)해 main에 머지. 대칭키(HMAC) 경로 위조내성은 운영정책 의존(Ed25519-only 배포 시 닫힘).
- **알려진 부채(README에 정직히, 이 웨이브에서 수리 안 함):** `scripts/dwm_*.py` ~66K LOC 이중 엔진
  (depone/ 패키지와 병존, 테스트 0%), CLAUDE.md "no pyproject" 불변식 ↔ 실제 pyproject.toml 자기모순.
  이것들은 **릴리스 범위 밖 기술부채로 명시**하고 건드리지 않는다(witnessd에서 out-of-scope 울타리 친 것과 동일 규율).

**불변식(변경 금지):** Depone은 계속 **비실행**(subprocess 에이전트 실행·team-run 루프 추가 금지 —
closed PR #61 거부 사유). assurance 상향 불가. A3 등급 없음(operator DSSE=report-level 축). 보안 수리
(observer-provenance 게이팅)를 약화시키지 않는다.

---

## Task 0: 베이스라인 — 실제 테스트/게이트 커맨드 확정 (추측 금지)

- [ ] 테스트 러너 확정: `python3 -m pytest` vs `python3 -m unittest discover -s tests` 중 실제 동작하는 것
  (pyproject.toml `[project.optional-dependencies]`/`[tool.pytest]` 확인). 전체 그린 스냅샷 기록(예상 ~333 tests).
- [ ] 계약 게이트 확정: `python3 scripts/check_contract.py --tier changed`(또는 full) + `python3 scripts/dwm.py doctor`
  실제 커맨드·exit 확인.
- [ ] **witnessd 역방향 conformance**: witnessd가 이 Depone로 재도출하는지 —
  `cd /home/ubuntu/moonweave && make dogfood && make test` 그린 확인(계약 드리프트 없음 증거).

## Task 1: GitHub Actions CI — `.github/workflows/ci.yml`

witnessd의 CI 패턴(`/home/ubuntu/moonweave/witnessd/.github/workflows/ci.yml`)을 참고해 잡 구성:
- [ ] **unit** — Task 0에서 확정한 테스트 커맨드, Python 3.10 + 3.12 매트릭스. 외부 런타임 의존 없음
  (Depone은 stdlib + openssl; 필요 시 openssl은 러너 기본 제공).
- [ ] **contract** — `check_contract.py` + `dwm.py doctor` red 없음.
- [ ] **conformance(선택, 강력추천)** — witnessd를 public clone(`$RUNNER_TEMP/witnessd`, witnessd CI가
  Depone을 tree 밖에 clone한 것과 대칭)해서 witnessd의 `scripts/revalidate_w1.py`를 이 Depone 체크아웃으로
  재도출 → **양방향 드리프트 가드**. (witnessd CI는 Depone을, Depone CI는 witnessd를 서로 검증.)
- [ ] 각 잡 커맨드를 로컬에서 1회씩 실행해 그린 확인 후 커밋.

## Task 2: README 정직성 정리

- [ ] 현 README(184줄) 구조를 위 §Context 사실에 맞춰 정리. 필수 포함:
  1. **한 줄:** "non-executing verifier — re-derives A0/A1/A2 from signed evidence bytes, offline, cannot raise the grade."
  2. **2제품 관계:** witnessd(실행기)↔Depone(검증기), 유일 결합=증거 계약. witnessd 링크.
  3. **보안 수리 이력:** P0 위조 결함 → PR #62 수리(정직히, 숨기지 않음 — "우리가 우리 결함을 잡아 고쳤다"는 신뢰 서사).
  4. **정직한 한계:** HMAC 경로 위조내성=운영정책 의존, 투명성로그/Sigstore A3 미구현, dwm 이중엔진 기술부채.
  5. **과대주장 금지 검사:** "unforgeable", "first real A2", "certified"를 달성 주장으로 쓰지 않는다
     (총리뷰 헤드라인: "지금 상태로 unforgeable 마케팅하면 첫 실사에서 붕괴").
- [ ] `grep -rniE "unforgeable|first real A2|certified" README.md`가 달성 주장으로 잡히면 실패.

## Task 3: v0.1.0 태그

- [ ] 최종 그린(아래 Matrix) → `git tag -a v0.1.0 -m "..."`. 태그 메시지: 정체(비실행 검증기),
  보안 수리 이력 1줄, 알려진 한계 3줄. **push는 사용자**(`git push origin v0.1.0`).
- [ ] pyproject.toml version이 0.1.0인지 확인(이미 0.1.0). PyPI 배포는 **이 웨이브 범위 밖**
  (witnessd·Depone 계약 안정화 후 별도 결정).

## Final Validation Matrix
```bash
cd /home/ubuntu/moonweave/depone
<Task0 테스트 커맨드>                      # 전체 그린
python3 scripts/check_contract.py --tier changed && python3 scripts/dwm.py doctor
cd /home/ubuntu/moonweave && make dogfood && make test   # witnessd 역방향 재도출 그린
cd /home/ubuntu/moonweave/depone && grep -rniE "unforgeable|first real A2|certified" README.md   # 달성주장 0
```

**Explicit Non-Changes:** 검증 로직 변경 금지 / Depone에 실행(subprocess/team-run) 추가 금지 /
dwm 이중엔진 리팩터 금지(부채로 명시만) / 보안 수리(observer-provenance) 약화 금지 / PyPI 배포 안 함 /
witnessd repo 수정 금지 / 태그 push는 사용자.
