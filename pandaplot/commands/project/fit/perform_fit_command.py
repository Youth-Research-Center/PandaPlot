import logging



class PerformFitCommand: #udno redo fitting
    def __init__(self, fit_panel):
        self.fit_results = None
        self.fit_panel = fit_panel
        self.logger = logging.getLogger(__name__)
