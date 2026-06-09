"""Unit tests para OperationsService — mocking total da Session.

Focam:
  - derive_supply_status thresholds
  - scoping por organization_id
  - shape do payload aninhado
  - relative_occupation + active_managers + supplies/resources/people
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from domain.auth.enums import Role
from domain.auth.jwt import CurrentUser
from domain.crisis.enums import CrisisStatus, CrisisType
from domain.errors.http import ResourceNotFoundError
from domain.models.beneficiary import Beneficiary
from domain.models.crisis import Crisis
from domain.models.inventory_item import InventoryItem
from domain.models.inventory_movement import InventoryMovement
from domain.models.resource_category import ResourceCategory
from domain.models.shelter import Shelter
from domain.models.shelter_stay import ShelterStay
from domain.schemas.enums import (
    BrazilianState,
    LotCategory,
    MovementDirection,
    MovementReason,
    ResourceUnit,
    SeverityLabel,
    ShelterStatus,
    ShelterType,
    SupplyStatus,
    VulnerabilityType,
)
from services.operations import OperationsService, derive_supply_status

_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# derive_supply_status thresholds                                             #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "current,maximum,expected",
    [
        (100, 100, SupplyStatus.SUFFICIENT),  # 1.0 -> Sufficient
        (50, 100, SupplyStatus.SUFFICIENT),  # 0.5  exato -> Sufficient (cota inclusiva)
        (49, 100, SupplyStatus.LOW),  # 0.49 -> Low
        (20, 100, SupplyStatus.LOW),  # 0.2  exato -> Low
        (19, 100, SupplyStatus.CRITICAL),  # 0.19 -> Critical
        (0, 100, SupplyStatus.CRITICAL),  # 0    -> Critical
        (50, None, SupplyStatus.SUFFICIENT),  # sem teto -> Sufficient
        (0, None, SupplyStatus.SUFFICIENT),
    ],
)
def test_derive_supply_status_thresholds(current, maximum, expected):
    assert derive_supply_status(current, maximum) is expected


# --------------------------------------------------------------------------- #
# Fixtures helpers                                                            #
# --------------------------------------------------------------------------- #


def _shelter(*, org=None, capacity=100, occupation=25) -> Shelter:
    return Shelter(
        id=uuid.uuid4(),
        organization_id=org,
        responsible_user_id=uuid.uuid4(),
        created_by=uuid.uuid4(),
        name="Abrigo X",
        address="Rua Y, 1",
        city="Maceio",
        state=BrazilianState.AL,
        capacity=capacity,
        occupation=occupation,
        shelter_type=ShelterType.INSTITUTIONAL,
        status=ShelterStatus.ACTIVE,
        verified=True,
    )


def _crisis(shelters: list[Shelter] | None = None) -> Crisis:
    c = Crisis(
        id=uuid.uuid4(),
        name="Crise Teste",
        type=CrisisType.FLOOD,
        status=CrisisStatus.ACTIVE,
        state=BrazilianState.AL,
        city="Maceio",
        severity_initial=3,
        created_by=uuid.uuid4(),
        created_at=_NOW,
        updated_at=_NOW,
    )
    for s in shelters or []:
        c.shelters.append(s)
    return c


def _viewer(*, org=None, dev=False) -> CurrentUser:
    return CurrentUser(
        id=uuid.uuid4(),
        roles=[Role.DEV if dev else Role.SHELTER_MANAGER],
        organization_id=org,
    )


def _make_session_for(crisis: Crisis, *, loaders: dict | None = None):
    """Returns a MagicMock session that:
    - .scalar(...) returns the crisis
    - .execute(...).all() returns rows per the optional `loaders` dict
      keyed in call order: ['supplies', 'movements', 'people', 'managers']
    """
    session = MagicMock()
    session.scalar.return_value = crisis

    if loaders is None:
        loaders = {"supplies": [], "movements": [], "people": [], "managers": []}

    call_sequence = ["supplies", "movements", "people", "managers"]
    return_iter = iter(call_sequence)

    def _execute_side_effect(*_args, **_kwargs):
        key = next(return_iter)
        result = MagicMock()
        result.all.return_value = loaders.get(key, [])
        return result

    session.execute.side_effect = _execute_side_effect
    return session


# --------------------------------------------------------------------------- #
# Scoping                                                                     #
# --------------------------------------------------------------------------- #


def test_404_when_crisis_does_not_exist():
    session = MagicMock()
    session.scalar.return_value = None

    with pytest.raises(ResourceNotFoundError):
        OperationsService(session).get_crisis_operations(
            uuid.uuid4(), _viewer(dev=True)
        )


def test_dev_sees_all_shelters_regardless_of_org():
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    crisis = _crisis(
        shelters=[
            _shelter(org=org_a),
            _shelter(org=org_b),
            _shelter(org=None),
        ]
    )
    session = _make_session_for(crisis)

    result = OperationsService(session).get_crisis_operations(
        crisis.id, _viewer(dev=True)
    )

    assert len(result.shelters) == 3


def test_shelter_manager_only_sees_own_org_shelters():
    my_org = uuid.uuid4()
    other_org = uuid.uuid4()
    mine = _shelter(org=my_org)
    others = _shelter(org=other_org)
    no_org = _shelter(org=None)
    crisis = _crisis(shelters=[mine, others, no_org])
    session = _make_session_for(crisis)

    result = OperationsService(session).get_crisis_operations(
        crisis.id, _viewer(org=my_org)
    )

    assert {s.id for s in result.shelters} == {mine.id}


def test_shelter_manager_without_org_sees_nothing():
    crisis = _crisis(shelters=[_shelter(org=uuid.uuid4())])
    session = _make_session_for(crisis)

    result = OperationsService(session).get_crisis_operations(
        crisis.id, _viewer(org=None)
    )

    assert result.shelters == []


# --------------------------------------------------------------------------- #
# Payload shape                                                                #
# --------------------------------------------------------------------------- #


def _make_category(
    *, name="alimento_nao_perecivel", lot=LotCategory.ESSENCIAIS, unit=ResourceUnit.KG
):
    return ResourceCategory(
        id=uuid.uuid4(),
        name=name,
        unit=unit,
        lot_category=lot,
        description=None,
    )


def _make_item(shelter_id, category_id, *, current=300, maximum=1000):
    return InventoryItem(
        id=uuid.uuid4(),
        shelter_id=shelter_id,
        category_id=category_id,
        quantity_current=current,
        quantity_max=maximum,
    )


def _make_movement(
    shelter_id,
    category_id,
    *,
    direction=MovementDirection.IN,
    reason=MovementReason.DONATION,
    quantity=100,
    destination_shelter_id=None,
):
    m = InventoryMovement(
        shelter_id=shelter_id,
        category_id=category_id,
        direction=direction,
        quantity=quantity,
        reason=reason,
        source=None,
        notes=None,
        destination_shelter_id=destination_shelter_id,
        created_by=uuid.uuid4(),
    )
    m.id = uuid.uuid4()
    m.created_at = _NOW
    return m


def _make_beneficiary(*, name="John Doe", cpf="123.456.789-00", age=30):
    return Beneficiary(
        id=uuid.uuid4(),
        cpf=cpf,
        name=name,
        age=age,
        vulnerability=VulnerabilityType.DISABLED,
    )


def _make_stay(shelter_id, beneficiary_id):
    return ShelterStay(
        id=uuid.uuid4(),
        beneficiary_id=beneficiary_id,
        shelter_id=shelter_id,
        checked_out_at=None,
    )


def test_full_payload_shape_with_one_shelter():
    # 135/150 = 0.9 — bem acima do limiar 0.85 -> ALTA sem ambiguidade
    shelter = _shelter(capacity=150, occupation=135)
    crisis = _crisis(shelters=[shelter])
    rice = _make_category(name="alimento_nao_perecivel", lot=LotCategory.ESSENCIAIS)
    water = _make_category(
        name="agua_potavel", lot=LotCategory.ESSENCIAIS, unit=ResourceUnit.L
    )

    item_rice = _make_item(shelter.id, rice.id, current=300, maximum=1000)  # Low
    item_water = _make_item(shelter.id, water.id, current=200, maximum=500)  # 0.4 Low
    mov_in = _make_movement(
        shelter.id, rice.id, direction=MovementDirection.IN, quantity=100
    )
    beneficiary = _make_beneficiary()
    stay = _make_stay(shelter.id, beneficiary.id)

    session = _make_session_for(
        crisis,
        loaders={
            "supplies": [(item_rice, rice), (item_water, water)],
            "movements": [(mov_in, rice)],
            "people": [(beneficiary, stay)],
            "managers": [(shelter.id, 12)],
        },
    )

    result = OperationsService(session).get_crisis_operations(
        crisis.id, _viewer(dev=True)
    )

    assert result.name == crisis.name
    assert result.city == crisis.city
    assert len(result.shelters) == 1
    block = result.shelters[0]
    assert block.name == shelter.name
    assert block.capacity == 150
    assert block.current_occupancy == 135
    assert block.relative_occupation == pytest.approx(135 / 150)
    assert block.severity is SeverityLabel.ALTA
    assert block.active_managers == 12

    # supplies
    assert len(block.supplies) == 2
    rice_supply = next(s for s in block.supplies if s.name == "alimento_nao_perecivel")
    assert rice_supply.status is SupplyStatus.LOW  # 300/1000 = 0.3 -> LOW
    assert rice_supply.lot_category is LotCategory.ESSENCIAIS
    assert rice_supply.max_capacity == 1000

    # resources
    assert len(block.resources) == 1
    res = block.resources[0]
    assert res.type is MovementDirection.IN
    assert res.category is LotCategory.ESSENCIAIS
    assert res.name == "alimento_nao_perecivel"
    assert res.destined_to is None

    # people
    assert len(block.people) == 1
    person = block.people[0]
    assert person.name == "John Doe"
    assert person.cpf == "123.456.789-00"
    assert person.vulnerabilities is VulnerabilityType.DISABLED


def test_transfer_out_movement_includes_destination_shelter_name():
    sender = _shelter(capacity=100, occupation=20)
    receiver = _shelter(capacity=80, occupation=10)
    receiver.name = "Abrigo Destino"
    crisis = _crisis(shelters=[sender, receiver])
    cat = _make_category()

    transfer = _make_movement(
        sender.id,
        cat.id,
        direction=MovementDirection.OUT,
        reason=MovementReason.TRANSFER_OUT,
        destination_shelter_id=receiver.id,
        quantity=50,
    )

    session = _make_session_for(
        crisis,
        loaders={
            "supplies": [],
            "movements": [(transfer, cat)],
            "people": [],
            "managers": [],
        },
    )

    result = OperationsService(session).get_crisis_operations(
        crisis.id, _viewer(dev=True)
    )

    sender_block = next(b for b in result.shelters if b.id == sender.id)
    assert len(sender_block.resources) == 1
    movement = sender_block.resources[0]
    assert movement.type is MovementDirection.OUT
    assert movement.destined_to == "Abrigo Destino"


def test_shelter_with_no_capacity_has_relative_occupation_zero():
    shelter = _shelter(capacity=0, occupation=0)
    crisis = _crisis(shelters=[shelter])
    session = _make_session_for(crisis)

    result = OperationsService(session).get_crisis_operations(
        crisis.id, _viewer(dev=True)
    )

    assert result.shelters[0].relative_occupation == 0.0
    assert result.shelters[0].severity is SeverityLabel.INATIVO


def test_active_managers_defaults_to_zero_when_no_users_shelters_row():
    shelter = _shelter()
    crisis = _crisis(shelters=[shelter])
    session = _make_session_for(crisis)  # managers loader vazio

    result = OperationsService(session).get_crisis_operations(
        crisis.id, _viewer(dev=True)
    )

    assert result.shelters[0].active_managers == 0
