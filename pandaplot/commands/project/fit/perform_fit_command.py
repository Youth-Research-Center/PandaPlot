import logging



class PerformFitCommand:
    def __init__(self, fit_panel):
        self.fit_results = None
        self.fit_panel = fit_panel
        self.logger = logging.getLogger(self.__class__.__name__)
    #TODO: add undo and redo logic