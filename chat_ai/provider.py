"""Application wording around the shared provider; no authorization decisions."""
from chat_ai_assistant.provider import ChatAIModelService
from chat_ai_assistant.clarifications import MESSAGES, message_language

APPLICATION_MESSAGES = {
    'fr': {
        'missing_details': 'Précisez le projet, le document, le client ou la période recherchée (avec l’année).',
        'ambiguous_metric': 'Parlez-vous des encaissements, des dépenses, du bénéfice, du budget ou des devis validés ? Pour quelle période ?',
        'unsupported': 'Précisez ce que vous souhaitez faire dans Management Projet, ou utilisez /aide pour voir les fonctions disponibles.',
    },
    'en': {
        'missing_details': 'Please specify the project, record, customer or reporting period (including the year).',
        'ambiguous_metric': 'Do you mean receipts, expenses, profit, budget or validated estimates? For which period?',
        'unsupported': 'Please clarify what you want to do in Management Projet, or use /help to see the available actions.',
    },
}


class ChatAIManagementModelService(ChatAIModelService):
    def __init__(self, config, interface_language='fr'):
        super().__init__(config)
        self.interface_language = 'en' if interface_language == 'en' else 'fr'

    def choose(self, messages, tools, cancel=None):
        action, usage = super().choose(messages, tools, cancel)
        if action.get('tool') == 'clarify':
            reason = next((reason for variants in MESSAGES.values()
                           for reason, text in variants.items() if text == action.get('message')), None)
            if reason:
                question = next((message['content'] for message in reversed(messages)
                                 if message['role'] == 'user'), '')
                language = message_language(question, self.interface_language)
                action = {**action, 'message': APPLICATION_MESSAGES[language][reason]}
        return action, usage
