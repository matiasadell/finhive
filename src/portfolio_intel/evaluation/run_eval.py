from __future__ import annotations

from portfolio_intel.data.store import load_portfolio_data
from portfolio_intel.evaluation.golden_set import load_golden_set
from portfolio_intel.evaluation.metrics import pass_rate, run_golden_set


def _try_log_to_mlflow(results: list[dict], rate: float) -> None:
    try:
        import mlflow

        mlflow.set_tracking_uri("databricks")
        mlflow.set_experiment("/Shared/portfolio-intel-eval")
        with mlflow.start_run():
            mlflow.log_metric("golden_set_pass_rate", rate)
            for r in results:
                mlflow.log_metric(f"check_{r['id']}", 1.0 if r["passed"] else 0.0)
        print("Resultado logueado en MLflow (/Shared/portfolio-intel-eval).")
    except Exception as e:  # noqa: BLE001 - best-effort, sin Databricks acá esto falla siempre
        print(
            f"(No se pudo loguear a MLflow -- esperado en esta máquina de "
            f"desarrollo sin conexión a Databricks: {e})"
        )


def main() -> None:
    golden_set = load_golden_set()
    df = load_portfolio_data().get_use_cases()
    results = run_golden_set(golden_set, df)
    rate = pass_rate(results)

    print(f"Golden set: {sum(r['passed'] for r in results)}/{len(results)} checks pasaron "
          f"({rate:.0%})\n")
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {r['id']} ({r['check']}): {r['detail']}")

    _try_log_to_mlflow(results, rate)


if __name__ == "__main__":
    main()
