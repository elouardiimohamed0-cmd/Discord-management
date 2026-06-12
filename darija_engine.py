"""
Authentic Moroccan Darija (Darija Maghribia) Engine for Discord Bot
Based on rich vocabulary dataset with 12,000+ sentences
Features: Natural code-switching, human-like fillers, contextual responses
"""

import random
import re
from collections import defaultdict

class DarijaEngine:
    """
    Human-like Darija response generator that mixes Darija, French, and English
    naturally - just like real Moroccans do in conversation.
    """

    def __init__(self, vocabulary_file=None):
        # Core vocabulary loaded from dataset
        self.vocab = self._load_default_vocab()

        # Human-like fillers and expressions (from dataset analysis)
        self.fillers = [
            "safi", "ah", "wakha", "wa", "yallah", "ewa", "oh", "lla", 
            "ayeh", "wayeh", "hmm", "hh", "hahaha", "oh wow", "ya salam",
            "bessa7", "sara7a", "f lwa9i3", "f7al", "b7al", "3la 7sab",
            "wakha hakkak", "ghir", "tani", "daba", "men ba3d", "merra merra"
        ]

        # Sentence starters for human feel
        self.starters = [
            "ana", "rah", "wach", "3lach", "kan", "ghadi", "koun", 
            "khlini", "sir", "nta", "nti", "hadi", "hadchi", "dakchi",
            "b7al", "f7al", "3la", "men", "w", "o", "walakin", "ila"
        ]

        # Common expressions for natural flow
        self.expressions = {
            'agreement': [
                "mttaf9 m3ak", "3ndk l7e99", "kanDen bessa7", "sara7a hadchi s7i7",
                "wakha hakkak", "ayeh", "wayeh", "ah", "safi"
            ],
            'disagreement': [
                "machi s7i7", "ma3ndekch l7e99", "hadchi machi 3adil",
                "m39oula", "kanDen hadchi khayb", "lla hadchi machi hakkak"
            ],
            'confusion': [
                "mafhemtch", "ma3rftch", "shno hadchi?", "ach hadchi?",
                "kan7ess b7al", "hadchi kaytllef", "mafhmtch mzyan"
            ],
            'emotion_positive': [
                "ana fr7an", "kayban zwin", "hadchi mezian", "zwin bzzaf",
                "ra2i3", "3aDim", "ghazal", "ban lia mezian"
            ],
            'emotion_negative': [
                "ana mkta2eb", "hadchi khayb", "mazal", "machi mezian",
                "kan7ess b7al", "hadchi kaykhle3", "safi hadchi me7en"
            ],
            'thinking': [
                "kanfkker", "tanDen", "ma3rftch", "khlini nfekker",
                "bllati nchof", "kanDen hadchi", "f7al"
            ]
        }

        # Code-switching: English words Moroccans naturally use
        self.english_loanwords = [
            "ok", "okay", "sorry", "please", "thanks", "hello", "bye",
            "good", "bad", "nice", "cool", "happy", "sad", "love",
            "problem", "message", "phone", "email", "facebook", "google",
            "youtube", "wifi", "internet", "computer", "pizza", "taxi",
            "hotel", "restaurant", "weekend", "meeting", "project",
            "party", "birthday", "manager", "password", "online", "offline"
        ]

        # Code-switching: French words (very common in Darija)
        self.french_loanwords = [
            "merci", "pardon", "excuse", "bon", "mauvais", "tres",
            "beaucoup", "un peu", "oui", "non", "avec", "sans", "pour",
            "et", "ou", "mais", "si", "alors", "donc", "parce", "quoi",
            "qui", "ou", "quand", "comment", "pourquoi", "combien",
            "cafe", "telephone", "portable", "ordinateur", "internet",
            "probleme", "question", "reponse", "idee", "travail", "maison",
            "voiture", "argent", "temps", "jour", "nuit", "soir", "matin"
        ]

        # Human typing patterns (imperfections make it real)
        self.typing_quirks = {
            'repeat_letters': 0.05,      # 5% chance to repeat letters ("sooo", "yaaah")
            'omit_spaces': 0.03,         # 3% chance to omit spaces
            'use_numbers': 0.15,         # 15% chance to use numbers for sounds (3 for ع, 7 for ح)
            'lowercase_start': 0.20,      # 20% chance to start lowercase
            'multiple_punctuation': 0.10,  # 10% chance for "!!" or "??"
            'ellipsis': 0.08,            # 8% chance for "..."
        }

        # Response delay simulation (human typing speed)
        self.typing_speed = {
            'fast': (1, 3),      # 1-3 seconds for short replies
            'normal': (3, 8),    # 3-8 seconds for medium
            'slow': (8, 15),     # 8-15 seconds for thinking
        }

    def _load_default_vocab(self):
        """Load the default vocabulary from the dataset structure."""
        return {
            'greetings': {
                'formal': ["Salam a likom", "Ahlan wa sahlan", "Sba7 lkhir", "Msa lkhir"],
                'casual': ["Salam", "Ahlan", "Sba7 nnour", "Kidayr?", "Wach kat3awd?"],
                'friendly': ["Salam 7bibi", "Ahlan ya 3zizi", "Kidayr l7bib?", "Wach nta bikhir?"]
            },
            'farewells': {
                'formal': ["Bslama", "Allah y3awn", "Msa lkhir", "Nchoufouk men ba3d"],
                'casual': ["Safi", "Yallah", "Thella", "Bslama 3likom"],
                'friendly': ["Bslama 7bibi", "Nchoufouk ghdda", "Yallah ntl9aw men ba3d"]
            },
            'how_are_you': {
                'ask': ["Kidayr?", "Wach kat3awd?", "Kif rask?", "Wach nta bikhir?", "Kidayr l7al?"],
                'respond_good': ["Ana bikhir", "Alhamdulillah", "Kolchi mezian", "Ana wajd"],
                'respond_bad': ["Mazal", "Machi bikhir", "3yit", "Daz lia nhar khayb"]
            },
            'thanks': {
                'give': ["Chokran", "Chokran bzzaf", "Chokran 3la kollchi", "Allah ykhllik"],
                'receive': ["Walo", "Machi mochkil", "3la rwah", "Hania", "Safi"]
            },
            'agreement': ["Wakha", "Mttaf9", "Ayeh", "Safi", "3ndk l7e99", "KanDen bessa7"],
            'disagreement': ["Machi s7i7", "Ma3ndekch l7e99", "Hadchi machi 3adil", "M39oula"],
        }

    def _add_human_typing(self, text):
        """Add human-like typing imperfections to make it feel real."""
        words = text.split()
        result = []

        for word in words:
            if random.random() < self.typing_quirks['repeat_letters'] and len(word) > 2:
                if word[-1] in 'aeiou':
                    word = word + word[-1] * random.randint(1, 2)
            result.append(word)

        text = ' '.join(result)

        if random.random() < self.typing_quirks['use_numbers']:
            text = text.replace('3', '3').replace('7', '7').replace('9', '9')

        if random.random() < self.typing_quirks['multiple_punctuation']:
            if '!' in text:
                text = text.replace('!', '!!' if random.random() > 0.5 else '!!!')
            if '?' in text:
                text = text.replace('?', '??' if random.random() > 0.5 else '???')

        if random.random() < self.typing_quirks['ellipsis']:
            text = text.replace('.', '...', 1)

        return text

    def _add_filler(self, text, probability=0.3):
        """Add natural fillers before or after sentences."""
        if random.random() < probability:
            filler = random.choice(self.fillers)
            position = random.choice(['before', 'after', 'both'])

            if position == 'before':
                text = f"{filler}, {text}"
            elif position == 'after':
                text = f"{text}, {filler}"
            else:
                text = f"{filler}, {text}, {filler}"

        return text

    def _code_switch(self, text, probability=0.25):
        """Naturally mix English or French words (authentic Moroccan behavior)."""
        words = text.split()
        result = []

        for i, word in enumerate(words):
            if random.random() < probability and len(word) > 3:
                if random.random() < 0.6:
                    loan = random.choice(self.english_loanwords)
                else:
                    loan = random.choice(self.french_loanwords)

                if i > 0 and i < len(words) - 1:
                    result.append(loan)
                    continue
            result.append(word)

        return ' '.join(result)

    def _add_expression(self, text, emotion=None):
        """Add emotional expressions for human feel."""
        if emotion and emotion in self.expressions:
            expr = random.choice(self.expressions[emotion])
            if random.random() < 0.5:
                text = f"{expr}, {text}"
            else:
                text = f"{text}, {expr}"
        return text

    def generate_greeting(self, familiarity='casual', time_of_day=None):
        """Generate a natural greeting."""
        if time_of_day == 'morning':
            base = random.choice(["Sba7 lkhir", "Sba7 nnour", "Sba7 l3asal"])
        elif time_of_day == 'evening':
            base = random.choice(["Msa lkhir", "Msa nnour"])
        else:
            base = random.choice(self.vocab['greetings'][familiarity])

        response = self._add_filler(base, probability=0.4)
        response = self._add_human_typing(response)

        if random.random() < 0.4:
            followup = random.choice([
                "kidayr?", "wach kat3awd?", "kif rask?", 
                "wach nta bikhir?", "kidayr l7al?"
            ])
            response = f"{response} {followup}"

        return response

    def generate_response(self, intent, context=None, emotion=None):
        """Generate a contextual response based on intent."""

        if intent == 'greeting':
            return self.generate_greeting()

        elif intent == 'how_are_you':
            if context == 'asking':
                return self._add_filler(random.choice(self.vocab['how_are_you']['ask']))
            else:
                if emotion == 'positive':
                    base = random.choice(self.vocab['how_are_you']['respond_good'])
                elif emotion == 'negative':
                    base = random.choice(self.vocab['how_are_you']['respond_bad'])
                else:
                    base = random.choice(self.vocab['how_are_you']['respond_good'] + 
                                         self.vocab['how_are_you']['respond_bad'])
                return self._add_expression(self._add_filler(base), emotion)

        elif intent == 'thanks':
            if context == 'giving':
                base = random.choice(self.vocab['thanks']['give'])
            else:
                base = random.choice(self.vocab['thanks']['receive'])
            return self._add_filler(base, probability=0.5)

        elif intent == 'agreement':
            base = random.choice(self.vocab['agreement'])
            return self._add_expression(self._add_filler(base), 'agreement')

        elif intent == 'disagreement':
            base = random.choice(self.vocab['disagreement'])
            return self._add_expression(self._add_filler(base), 'disagreement')

        elif intent == 'farewell':
            base = random.choice(self.vocab['farewells']['casual'])
            return self._add_filler(base, probability=0.6)

        elif intent == 'thinking':
            base = random.choice(self.expressions['thinking'])
            return self._add_filler(base, probability=0.7)

        elif intent == 'confusion':
            base = random.choice(self.expressions['confusion'])
            return self._add_filler(base, probability=0.6)

        else:
            base = random.choice([
                "Safi fhemt", "Wakha nchouf", "KanDen hadchi", 
                "Ma3rftch", "Khlini nfekker", "Wakha hakkak"
            ])
            return self._add_filler(self._add_human_typing(base))

    def generate_natural_sentence(self, topic=None, length='medium'):
        """Generate a completely natural Darija sentence."""

        structures = {
            'short': [
                "{starter} {verb}.",
                "{filler}, {phrase}.",
                "{expression}.",
            ],
            'medium': [
                "{starter} {subject} {verb} {object}.",
                "{filler}, {subject} {verb} {preposition} {object}.",
                "{starter} {verb} {object}, {filler}.",
                "{expression}, {subject} {verb}.",
            ],
            'long': [
                "{starter} {subject} {verb} {object}, {conjunction} {subject2} {verb2} {object2}.",
                "{filler}, {subject} {verb} {object} {preposition} {location}, {filler}.",
                "{starter} {subject} {verb} {object}, {filler}, {conjunction} {expression}.",
            ]
        }

        subjects = ["ana", "nta", "nti", "hia", "howa", "7na", "ntoma", "homa", "chi wahd"]
        verbs = ["kan7ess", "kanDen", "kanfkker", "bghit", "mabghitich", "9der", "ma9derch", 
                 "n3ref", "ma3rftch", "kan3ich", "kankhdem", "kansm3", "kanchouf"]
        objects = ["hadchi", "dakchi", "chi haja", "chi wahd", "lkhdma", "ddar", "l7al", 
                   "lflous", "lwe9t", "nnass", "lkhobz", "lma", "l9hwa"]
        prepositions = ["f", "mn", "3la", "l", "m3a", "bl", "7it", "w"]
        locations = ["ddar", "lkhdma", "lmdrasa", "ssou9", "lpiscine", "lb7er", "ljbel"]
        conjunctions = ["w", "o", "walakin", "ila", "7it", "3lach"]

        structure = random.choice(structures.get(length, structures['medium']))

        sentence = structure.format(
            starter=random.choice(self.starters),
            subject=random.choice(subjects),
            subject2=random.choice(subjects),
            verb=random.choice(verbs),
            verb2=random.choice(verbs),
            object=random.choice(objects),
            object2=random.choice(objects),
            preposition=random.choice(prepositions),
            location=random.choice(locations),
            conjunction=random.choice(conjunctions),
            filler=random.choice(self.fillers),
            expression=random.choice(self.expressions['thinking']),
            phrase=random.choice(["safi", "wakha", "yallah", "ewa"])
        )

        sentence = self._add_filler(sentence, probability=0.4)
        sentence = self._add_human_typing(sentence)

        if random.random() < 0.2:
            sentence = self._code_switch(sentence)

        return sentence

    def respond_to_message(self, message_text, user_context=None):
        """
        Main entry point: analyze incoming message and generate human-like Darija response.

        Args:
            message_text: The incoming message (can be Darija, English, French, or mixed)
            user_context: Dict with user info (name, familiarity level, conversation history)

        Returns:
            dict with: {'text': response, 'typing_time': seconds, 'emotion': detected_emotion}
        """
        message_lower = message_text.lower()

        intent = self._detect_intent(message_lower)
        emotion = self._detect_emotion(message_lower)

        familiarity = user_context.get('familiarity', 'casual') if user_context else 'casual'

        if intent == 'greeting':
            response_text = self.generate_greeting(familiarity=familiarity)
        elif intent == 'question':
            response_text = self._answer_question(message_lower, familiarity)
        elif intent == 'how_are_you':
            response_text = self.generate_response('how_are_you', emotion=emotion)
        elif intent == 'thanks':
            response_text = self.generate_response('thanks', context='receiving')
        elif intent == 'farewell':
            response_text = self.generate_response('farewell')
        else:
            if random.random() < 0.6:
                response_text = self.generate_natural_sentence(length='medium')
            else:
                response_text = self.generate_response(intent, emotion=emotion)

        word_count = len(response_text.split())
        if word_count <= 3:
            typing_time = random.randint(1, 3)
        elif word_count <= 8:
            typing_time = random.randint(3, 7)
        else:
            typing_time = random.randint(7, 12)

        if random.random() < 0.3 and word_count > 5:
            typing_time += random.randint(2, 5)

        return {
            'text': response_text,
            'typing_time': typing_time,
            'emotion': emotion,
            'intent': intent
        }

    def _detect_intent(self, message):
        """Detect the intent of an incoming message."""
        if any(w in message for w in ['salam', 'ahlan', 'sba7', 'msa', 'hello', 'hi', 'bonjour', 'coucou']):
            return 'greeting'

        if any(w in message for w in ['kidayr', 'kifach', 'wach bikhir', 'how are', 'ca va', 'cv']):
            return 'how_are_you'

        if any(w in message for w in ['bslama', 'thella', 'bye', 'au revoir', 'bonne nuit', 'good night']):
            return 'farewell'

        if any(w in message for w in ['chokran', 'shokran', 'merci', 'thanks', 'thank you', 'barak']):
            return 'thanks'

        if any(w in message for w in ['wach', '3lach', 'fin', 'ch7al', 'imta', 'chkon', 'ach', 'chno', 'kifach', 'kidaz', 'kidayr']):
            return 'question'
        if '?' in message or message.startswith(('do ', 'are ', 'what ', 'where ', 'how ', 'why ', 'who ', 'which ', 'can ', 'could ')):
            return 'question'

        return 'statement'

    def _detect_emotion(self, message):
        """Detect emotional tone of message."""
        if any(w in message for w in ['fr7an', 'zwin', 'mezian', 'good', 'happy', 'great', 'excellent', 'love', 'like', 'nice', 'cool']):
            return 'positive'
        elif any(w in message for w in ['khayb', 'mkta2eb', '3yit', 'm7en', 'bad', 'sad', 'terrible', 'hate', 'angry', 'problem']):
            return 'negative'
        elif any(w in message for w in ['mafhemtch', 'ma3rftch', 'confused', 'what?', 'huh?', '??']):
            return 'confusion'
        return None

    def _answer_question(self, message, familiarity):
        """Generate an answer to a question."""
        if message.startswith('wach'):
            if random.random() < 0.7:
                return self._add_filler(random.choice(["Ayeh", "Wakha", "Ah", "Safi"]))
            else:
                return self._add_filler(random.choice(["Lla", "Machi", "Ma3ndekch l7e99"]))

        elif any(w in message for w in ['fin', 'where']):
            responses = [
                "Ma3rftch", "Khlini nfekker", "KanDen f ...", 
                "Safi fhemt, fin bghiti tmchi?"
            ]
            return self._add_filler(random.choice(responses))

        elif any(w in message for w in ['ch7al', 'how much', 'how many', 'how old']):
            responses = [
                "Ma3rftch ch7al", "KanDen chi ...", 
                "Khlini nchouf", "Safi, ch7al bghiti?"
            ]
            return self._add_filler(random.choice(responses))

        elif any(w in message for w in ['3lach', 'why', 'pourquoi']):
            responses = [
                "7it ...", "Ma3rftch 3lach", "KanDen 7it ...",
                "Hadchi kaytllef", "Safi, 3lach kat9elleb?"
            ]
            return self._add_filler(random.choice(responses))

        else:
            return self.generate_natural_sentence(length='medium')
