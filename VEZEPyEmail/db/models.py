class Mailbox:
    def __init__(self, id: int, user_id: int, name: str):
        self.id = id
        self.user_id = user_id
        self.name = name


class Message:
    def __init__(self, id: int, mailbox_id: int, subject: str, from_addr: str, date: str, flags: list[str], size: int, spam_score: float):
        self.id = id
        self.mailbox_id = mailbox_id
        self.subject = subject
        self.from_addr = from_addr
        self.date = date
        self.flags = flags
        self.size = size
        self.spam_score = spam_score
