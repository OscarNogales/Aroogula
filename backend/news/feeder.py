from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import json
import os



class NewsFeeder():

    def __init__(self, settings, bloomberg_bot, yahoo_bot, edgar_bot, forbes_bot):
        """
        Settings: file path for the program settings.
        """

        # Settings
        self.settings = settings
        self.settings_dict = settings.settings

        # Other configs
        self.scheduler = BackgroundScheduler(timezone="America/New_York")


        # BloombergBot
        self.bb_bot = bloomberg_bot

        self.scheduler.add_job(
                self.bb_bot.execute_news_pull,
                trigger=CronTrigger(day_of_week="mon-fri", hour="9-16", minute="1-59/30", timezone="America/New_York"),
                id="bloomberg_job",
                replace_existing=True
            )
        

        # YahooBot
        self.yhoo_bot = yahoo_bot

        self.scheduler.add_job(
            self.yhoo_bot.execute_news_pull,
            CronTrigger(day_of_week="mon-fri", hour="9-16", minute="0,7,30", timezone="America/New_York"),
            id="yahoo_job",
            replace_existing=True
        )
        
        # EDGARBot
        self.edgar_bot = edgar_bot

        self.scheduler.add_job(
        self.edgar_bot.execute_filings_pull, 
        trigger=CronTrigger(day_of_week="mon-fri", hour="9-16", minute="0,15,30,45", timezone="America/New_York"),
        id="edgar_job",
        replace_existing=True
        )

        # ForbesBot

        self.forbes_bot = forbes_bot
        
        self.scheduler.add_job(
        self.forbes_bot.execute_news_pull, 
        trigger=CronTrigger(day_of_week="mon-fri", hour="9-16", minute="0,15,30,45", timezone="America/New_York"),
        id="forbes_job",
        replace_existing=True
        )

        # Scheduler controllers

        self._sync_scheduler()
        self.scheduler.start()

        
        
    def _sync_scheduler(self):
        
        # Bloomberg
        if self.settings_dict.get("Bloomberg bot") == True:
            self.scheduler.resume_job('bloomberg_job')
        else:
            self.scheduler.pause_job('bloomberg_job')

        # Yahoo
        if self.settings_dict.get("Yahoo bot") == True:
            self.scheduler.resume_job('yahoo_job')
        else:
            self.scheduler.pause_job('yahoo_job')

        # Forbes
        if self.settings_dict.get("Forbes bot") == True:
            self.scheduler.resume_job('forbes_job')
        else:
            self.scheduler.pause_job("forbes_job")

        # EDGAR
        if self.settings_dict.get("EDGAR bot") == True:
            self.scheduler.resume_job('edgar_job')
        else:
            self.scheduler.pause_job("edgar_job")


    # Turn on/off bots
    def toggle_BloombergBot(self, turn_on: bool):
        self.settings_dict["Bloomberg bot"] = turn_on
        self.settings.update_settings(self.settings_dict)
        self._sync_scheduler()

    def toggle_YahooBot(self, turn_on: bool):
        self.settings_dict["Yahoo bot"] = turn_on
        self.settings.update_settings(self.settings_dict)
        self._sync_scheduler()

    def toggle_EDGARBot(self, turn_on: bool):
        self.settings_dict["EDGAR bot"] = turn_on
        self.settings.update_settings(self.settings_dict)
        self._sync_scheduler()

    def toggle_ForbesBot(self, turn_on: bool):
        self.settings_dict["Forbes bot"] = turn_on
        self.settings.update_settings(self.settings_dict)
        self._sync_scheduler()
