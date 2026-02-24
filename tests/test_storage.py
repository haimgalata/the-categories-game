from typing import Any, Dict, List, Tuple

from src import storage
from src.models import Answer, GameState, PlayerStats, Round, new_answer, new_game_state, new_round


class FakeCollection:
    def __init__(self) -> None:
        self.update_calls: List[Tuple[Any, Any, Any]] = []
        self.insert_calls: List[Any] = []
        self.find_one_result: Any = None
        self.index_calls: List[Any] = []

    def update_one(self, filt: Dict[str, Any], update: Dict[str, Any], upsert: bool = False) -> None:
        self.update_calls.append((filt, update, upsert))

    def insert_one(self, doc: Dict[str, Any]) -> None:
        self.insert_calls.append(doc)

    def find_one(self, filt: Dict[str, Any]) -> Any:
        return self.find_one_result

    def create_index(self, keys: Any, unique: bool = False) -> None:
        self.index_calls.append((keys, unique))


class FakeDB:
    def __init__(self) -> None:
        self.collections: Dict[str, FakeCollection] = {
            "games": FakeCollection(),
            "rounds": FakeCollection(),
            "answers": FakeCollection(),
            "players": FakeCollection(),
        }

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections[name]


def test_ensure_indexes_calls_create_index() -> None:
    """
    Params: none.
    Returns: None.
    Description: ensure_indexes creates required indexes.
    Examples:
        Input: FakeDB
        Output: create_index called on answers and rounds
    """
    db = FakeDB()
    storage.ensure_indexes(db)
    assert len(db["answers"].index_calls) == 2
    assert len(db["rounds"].index_calls) == 1


def test_save_game_upserts() -> None:
    """
    Params: none.
    Returns: None.
    Description: save_game upserts by game_id.
    Examples:
        Input: GameState
        Output: update_one called with upsert=True
    """
    db = FakeDB()
    storage._DB = db
    game: GameState = new_game_state(1001)
    storage.save_game(game)
    filt, update, upsert = db["games"].update_calls[0]
    assert filt == {"game_id": game.game_id}
    assert upsert is True
    assert "$set" in update


def test_save_round_upserts() -> None:
    """
    Params: none.
    Returns: None.
    Description: save_round upserts by round_id.
    Examples:
        Input: Round
        Output: update_one called with upsert=True
    """
    db = FakeDB()
    storage._DB = db
    rnd: Round = new_round("g1", 1, "C", "City")
    storage.save_round(rnd)
    filt, update, upsert = db["rounds"].update_calls[0]
    assert filt == {"round_id": rnd.round_id}
    assert upsert is True
    assert "$set" in update


def test_save_answer_inserts() -> None:
    """
    Params: none.
    Returns: None.
    Description: save_answer inserts a document.
    Examples:
        Input: Answer
        Output: insert_one called with doc
    """
    db = FakeDB()
    storage._DB = db
    ans: Answer = new_answer(
        game_id="g1",
        round_id="r1",
        user_id=7,
        raw_text="CaiHro",
        corrected_text="Cairo",
        valid=True,
        score=18,
        response_ms=12000,
        username="u",
        letter="C",
        category="City",
    )
    storage.save_answer(ans)
    doc = db["answers"].insert_calls[0]
    assert doc["game_id"] == "g1"
    assert doc["letter"] == "C"
    assert doc["category"] == "City"


def test_upsert_player_stats() -> None:
    """
    Params: none.
    Returns: None.
    Description: upsert_player_stats upserts by chat_id and user_id.
    Examples:
        Input: PlayerStats
        Output: update_one called with upsert=True
    """
    db = FakeDB()
    storage._DB = db
    stats = PlayerStats(chat_id=1, user_id=2, username="u")
    storage.upsert_player_stats(stats)
    filt, update, upsert = db["players"].update_calls[0]
    assert filt == {"chat_id": 1, "user_id": 2}
    assert upsert is True
    assert "$set" in update


def test_has_answer_been_used_true_false() -> None:
    """
    Params: none.
    Returns: None.
    Description: has_answer_been_used returns True when found.
    Examples:
        Input: find_one_result set
        Output: True
    """
    db = FakeDB()
    storage._DB = db
    db["answers"].find_one_result = None
    assert storage.has_answer_been_used("g1", "C", "City", "Cairo") is False
    db["answers"].find_one_result = {"_id": "x"}
    assert storage.has_answer_been_used("g1", "C", "City", "Cairo") is True
