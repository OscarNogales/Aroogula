def get_all_scheduler_jobs(services) -> list[dict]:
    all_jobs = []

    schedulers = [
        ("trade_analyzer", getattr(services.trade_analyzer, "scheduler", None)),
        ("news_feeder", getattr(services.news_feeder, "scheduler", None)),
        ("broker", getattr(services.broker, "scheduler", None)),
    ]

    for owner, scheduler in schedulers:
        if scheduler is None:
            continue

        for job in scheduler.get_jobs():
            all_jobs.append({
                "owner": owner,
                "id": job.id,
                "name": job.name,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            })

    return all_jobs