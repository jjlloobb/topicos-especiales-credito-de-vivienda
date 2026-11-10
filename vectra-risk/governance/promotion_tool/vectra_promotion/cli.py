"""CLI de `promotion-tool`. Sin subcomando de retiro (diferido por la demo). El token de Keycloak solo vive en memoria."""

import argparse
import shlex
import sys
import webbrowser
from collections.abc import Callable, Sequence
from pathlib import Path

import httpx

from vectra_promotion import commands
from vectra_promotion.api import GovernanceApi
from vectra_promotion.errors import PromotionError
from vectra_promotion.gitops import ENVS, PromotionRepo, Runner, system_runner
from vectra_promotion.login import login


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="promotion-tool")
    p.add_argument("--issuer", help="URL del realm de Keycloak (https://host/auth/realms/vectra)")
    p.add_argument("--api", help="base de F08 en el gateway (https://host/api/promotion)")
    p.add_argument("--repo", type=Path, default=Path("."), help="raiz del repositorio git")
    p.add_argument("--env", choices=ENVS, default="kind")
    p.add_argument("--diff-command", help="comando de solo lectura que recibe el render por stdin (p. ej. 'kubectl --context kind-vectra diff -f -')")
    p.add_argument("--gitops", default="vectra-risk/vectra-risk-gitops")
    p.add_argument("--chart", default="vectra-risk/model-serving/chart")
    p.add_argument("--base", default="main")
    p.add_argument("--helm", default="helm")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("list-promotable")
    sub.add_parser("create-promotion-pr").add_argument("model_version_id")
    sub.add_parser("post-activation-pr").add_argument("previous_version_id")
    sub.add_parser("rollback-pr").add_argument("model_version_id")
    activation = sub.add_parser("mark-active")
    activation.add_argument("model_version_id")
    activation.add_argument("--evidence", required=True)
    return p


def main(
    argv: Sequence[str] | None = None,
    *,
    open_browser: Callable[[str], object] = webbrowser.open,
    transport: httpx.BaseTransport | None = None,
    runner: Runner = system_runner,
) -> int:
    args = parser().parse_args(argv)
    try:
        repo = PromotionRepo(
            args.repo, shlex.split(args.diff_command or ""), args.env, args.gitops, args.chart, args.base, helm=args.helm, runner=runner
        ) if args.command != "list-promotable" else None
        if args.command == "post-activation-pr":
            print(commands.post_activation_pr(_need(repo), args.previous_version_id))  # noqa: T201
        elif args.command == "rollback-pr":
            print(commands.rollback_pr(_need(repo), args.model_version_id))  # noqa: T201
        else:
            if not args.issuer or not args.api:
                raise PromotionError("issuer_and_api_required")
            api = GovernanceApi(args.api, login(args.issuer, open_browser, transport=transport), transport)
            if args.command == "list-promotable":
                for m in commands.list_promotable(api):
                    print(m.model_version_id, m.state, m.inference_service)  # noqa: T201
            elif args.command == "create-promotion-pr":
                print(commands.create_promotion_pr(api, _need(repo), args.model_version_id))  # noqa: T201
            else:
                print(commands.mark_active(api, _need(repo), args.model_version_id, args.evidence))  # noqa: T201
    except PromotionError as error:
        print(f"promotion_tool_failed: {error}", file=sys.stderr)  # noqa: T201
        return 1
    return 0


def _need(repo: PromotionRepo | None) -> PromotionRepo:
    if repo is None:
        raise PromotionError("repo_required")
    return repo


if __name__ == "__main__":
    raise SystemExit(main())
