# Copyright [2025] [SOPTIM AG]
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

import numpy as np
from power_grid_model import ComponentType, MeasuredTerminalType, initialize_array

from cgmes2pgm_converter.common import (
    COMPONENT_TYPE,
    AbstractCgmesIdMapping,
    CgmesDataset,
    ConverterOptions,
    SymPowerType,
    Topology,
)

from ...component import AbstractPgmComponentBuilder

# short names for logging (d = debug, dd = debug deeper)
# change from logging.debug to logging.info when needed
log_d = logging.debug
log_dd = logging.debug
log_ddd = logging.debug


class SymPowerSensorIncompleteAppliance(AbstractPgmComponentBuilder):
    """
    Creates Power Sensors for Appliances that don't have a power sensor
    a power sensor using p_specified and q_specified from the appliances
    These values correspond to the ssh values
    """

    def __init__(
        self,
        cgmes_source: CgmesDataset,
        id_mapping: AbstractCgmesIdMapping,
        converter_options: ConverterOptions,
        data_type: str = "input",
    ):
        super().__init__(cgmes_source, id_mapping, converter_options, data_type)
        im = self._converter_options.measurement_substitution.incomplete_measurements
        conf_ssh = im.use_ssh
        conf_balance = im.use_balance
        self._is_active = conf_ssh.enable or conf_balance.enable

        self._ssh_enabled = conf_ssh.enable
        self._balance_enabled = conf_balance.enable

        self._ssh_sigma = conf_ssh.sigma * 1e6
        self._balance_sigma = conf_balance.sigma * 1e6

        self._topo = None

    def is_active(self) -> bool:
        return self._is_active

    def build_from_cgmes(self, input_data: dict) -> tuple[np.ndarray, dict | None]:

        self.update_incomplete_sensors(input_data)

        arr = initialize_array("input", ComponentType.sym_power_sensor, 0)
        return arr, None

    def update_incomplete_sensors(self, input_data: dict):
        """
        Find incomplete sensors, i.e.  P or Q is missing but was added as value 0.0,
        and try to determine a better value by looking at the appliances in the neighborhood.
        """

        self._topo = Topology(input_data, self._extra_info)

        sensors = input_data[ComponentType.sym_power_sensor]
        by_id = {s["id"]: s for s in sensors}

        for id_, tt in self._extra_info.items():
            _type = tt.get("_type")
            if _type in [SymPowerType.P_ZERO, SymPowerType.Q_ZERO]:
                sens = by_id.get(id_)
                if sens is None:
                    continue
                mtt = sens["measured_terminal_type"]
                obj_id = sens["measured_object"]
                obj = self._extra_info[obj_id]
                obj_type = obj.get("_type")
                obj_name = self._id_mapping.get_name_from_pgm(obj_id)
                topo_obj = self._topo[obj_id]
                ctype = topo_obj[COMPONENT_TYPE]
                pgm_obj = topo_obj[ctype]

                log_dd(
                    "Found sensor with zero p (%s) or q (%s): %s %s %s",
                    _type == SymPowerType.P_ZERO,
                    _type == SymPowerType.Q_ZERO,
                    sens["id"],
                    obj_type,
                    obj_name,
                )

                if mtt in [
                    MeasuredTerminalType.load,
                    MeasuredTerminalType.generator,
                    MeasuredTerminalType.shunt,
                ]:
                    node_id = pgm_obj["node"]
                    node_name = self._id_mapping.get_name_from_pgm(node_id)
                    log_ddd("\tat node %d / %s", node_id, node_name)
                    self._print_node(node_id)

                    self.find_better_appliance_measurement(sens, obj_id, mtt, _type)

                elif mtt in [
                    MeasuredTerminalType.branch_from,
                    MeasuredTerminalType.branch_to,
                ]:
                    from_node_id = pgm_obj["from_node"]
                    from_node_name = self._id_mapping.get_name_from_pgm(from_node_id)
                    log_ddd("\tfrom node %d / %s", from_node_id, from_node_name)
                    self._print_node(from_node_id)

                    to_node_id = pgm_obj["to_node"]
                    to_node_name = self._id_mapping.get_name_from_pgm(to_node_id)
                    log_ddd("\tto node %d / %s", to_node_id, to_node_name)
                    self._print_node(to_node_id)

                    self.find_better_branch_measurement(sens, obj_id, mtt, _type)

                elif mtt == MeasuredTerminalType.source:
                    # ignore sources, as they don't have p_specified or q_specified values
                    pass

                else:
                    raise ValueError(f"Unknown MeasuredTerminalType {mtt}")

    def find_better_appliance_measurement(
        self, sensor, appl_id, mtt: MeasuredTerminalType, _type: SymPowerType
    ):
        if mtt == MeasuredTerminalType.shunt:
            if _type == SymPowerType.P_ZERO and sensor["p_measured"] == 0.0:
                log_dd(
                    "\t\tSubstitute P value of 0.0 on shunt %d is valid",
                    appl_id,
                )
            else:
                log_d(
                    "\t\tNo better measurement found for sensor %d on shunt %d",
                    sensor["id"],
                    appl_id,
                )
        else:
            topo_appl = self._topo[appl_id]
            pgm_appl = topo_appl[topo_appl[COMPONENT_TYPE]]
            if (
                _type == SymPowerType.P_ZERO
                and sensor["p_measured"] == 0.0
                and self._ssh_enabled
            ):
                new_p = pgm_appl["p_specified"]
                self.set_new_sensor_p_value(
                    sensor, 1, new_p, self._ssh_sigma, SymPowerType.P_FROM_SSH
                )
            elif (
                _type == SymPowerType.Q_ZERO
                and sensor["q_measured"] == 0.0
                and self._ssh_enabled
            ):
                new_q = pgm_appl["q_specified"]
                self.set_new_sensor_q_value(
                    sensor, 1, new_q, self._ssh_sigma, SymPowerType.Q_FROM_SSH
                )
            else:
                log_d(
                    "\t\tNo better measurement found for sensor %d on appliance %d",
                    sensor["id"],
                    appl_id,
                )

    def find_better_branch_measurement(
        self,
        sensor,
        branch_id,
        mtt: MeasuredTerminalType,
        _type: SymPowerType,
    ):
        topo_branch = self._topo[branch_id]
        pgm_branch = topo_branch[topo_branch[COMPONENT_TYPE]]
        from_node_id = pgm_branch["from_node"]
        to_node_id = pgm_branch["to_node"]

        if self.find_better_branch_measurement_at_node(
            sensor, branch_id, from_node_id, "from", mtt, _type
        ):
            return

        if self.find_better_branch_measurement_at_node(
            sensor, branch_id, to_node_id, "to", mtt, _type
        ):
            return

        # no unambiguous value found
        log_d(
            "\t\tNo better measurement found for sensor %d on branch %d",
            sensor["id"],
            branch_id,
        )

    def find_better_branch_measurement_at_node(
        self,
        sensor,
        branch_id,
        node_id,
        direction: str,
        mtt: MeasuredTerminalType,
        _type: SymPowerType,
    ):

        # If there is only one branch (i.e. this branch) and otherwise only appliances are
        # connected to the node, then try to determine the missing measurement value
        # by looking at the balance of the appliances on the node.
        is_applicable, appliance_ids = self._node_has_one_branch_and_only_appliances(
            node_id,
        )
        if is_applicable:
            if len(appliance_ids) == 0:
                log_dd(
                    "\t\tSubstitute P value of 0.0 for sensor %d on branch %d is valid. No appliances on '%s'-node.",
                    sensor["id"],
                    branch_id,
                    direction,
                )
                return True

            if (
                self.are_appliances_only_shunts(appliance_ids)
                and _type == SymPowerType.P_ZERO
            ):
                if sensor["p_measured"] == 0.0:
                    log_dd(
                        "\t\tSubstitute P value of 0.0 for sensor %d on branch %d is valid. Only shunts on 'from'-node.",
                        sensor["id"],
                        branch_id,
                    )
                    return True

            p, q, p_mis, q_mis = self._calc_balance_from_appliances(appliance_ids)
            if _type == SymPowerType.P_ZERO and not p_mis and self._balance_enabled:
                sign = 1 if mtt == MeasuredTerminalType.branch_to else -1
                self.set_new_sensor_p_value(
                    sensor, sign, p, self._balance_sigma, SymPowerType.P_FROM_BALANCE
                )
                sensor_mirror = self.get_mirrored_sensor(sensor, branch_id)
                if sensor_mirror is not None:
                    # move negated value to the mirrored sensor, but keep the type at MIRRORED
                    self.set_new_sensor_p_value(
                        sensor_mirror,
                        sign * -1,
                        p,
                        self._balance_sigma,
                        SymPowerType.MIRRORED,
                    )
                return True
            if _type == SymPowerType.Q_ZERO and not q_mis and self._balance_enabled:
                sign = 1 if mtt == MeasuredTerminalType.branch_to else -1
                self.set_new_sensor_q_value(
                    sensor, sign, q, self._balance_sigma, SymPowerType.Q_FROM_BALANCE
                )
                sensor_mirror = self.get_mirrored_sensor(sensor, branch_id)
                if sensor_mirror is not None:
                    # move negated value to the mirrored sensor, but keep the type at MIRRORED
                    self.set_new_sensor_q_value(
                        sensor_mirror,
                        sign * -1,
                        q,
                        self._balance_sigma,
                        SymPowerType.MIRRORED,
                    )
                return True
        return False

    def are_appliances_only_shunts(self, appliances):
        for appl in appliances:
            if self._topo[appl]["component_type"] != ComponentType.shunt:
                return False
        return True

    def get_mirrored_sensor(self, sensor, branch_id):
        """
        If a sensor was mirrored to the other side of the branch, then a missing P or Q value
        will also be missing on the mirrored sensor. Return the mirrored sensor if it exists.
        """
        pgm_branch = self._topo[branch_id]
        s_from = pgm_branch.get("_sensor_p_from")
        s_to = pgm_branch.get("_sensor_p_to")
        if s_to is not None and s_from is not None:
            sensor_mirror = s_from if s_to["id"] == sensor["id"] else s_to
            mirror_id = sensor_mirror["id"]
            mirror_type = self._extra_info[mirror_id]["_type"]
            if mirror_type == SymPowerType.MIRRORED:
                return sensor_mirror
        return None

    def set_new_sensor_p_value(self, sensor, sign, p, p_sigma, _new_type: SymPowerType):
        old_p = sensor["p_measured"]
        sensor["p_measured"] = p * sign
        sensor["p_sigma"] = p_sigma
        self._extra_info[sensor["id"]]["_type"] = _new_type
        log_d(
            "\t\tSubstitute P value %f with %f for sensor %d",
            old_p,
            p * sign,
            sensor["id"],
        )

    def set_new_sensor_q_value(self, sensor, sign, q, q_sigma, _new_type: SymPowerType):
        old_q = sensor["q_measured"]
        sensor["q_measured"] = q * sign
        sensor["q_sigma"] = q_sigma
        self._extra_info[sensor["id"]]["_type"] = _new_type
        log_d(
            "\t\tSubstitute Q value %f with %f for sensor %d",
            old_q,
            q * sign,
            sensor["id"],
        )

    def _node_has_one_branch_and_only_appliances(self, node_id):
        topo_node = self._topo[node_id]
        branches = topo_node.get("_branches")
        appliances = []  # TODO: Move to a separate method
        appliances += topo_node.get(ComponentType.sym_gen, [])
        appliances += topo_node.get(ComponentType.sym_load, [])
        appliances += topo_node.get(ComponentType.shunt, [])
        # return len(branches) == 1 and len(appliances) > 0, appliances
        return len(branches) == 1, appliances

    def _calc_balance_from_appliances(self, appliances):
        meas = []
        for appl in appliances:
            item = self._topo[appl]
            mm = item.get("_sensor_p")
            if mm is not None:
                meas.append(mm)

        if len(meas) == 0:
            return np.nan, np.nan, True, True

        p = 0
        q = 0
        p_missing = False
        q_missing = False

        if len(meas) > 0:
            for me in meas:
                me_id = me["id"]
                p += me["p_measured"]
                q += me["q_measured"]
                extra = self._extra_info.get(me_id)
                if extra is not None:
                    _type = extra.get("_type")

                    # If for an appliance measurement either P or Q is missing,
                    # then the balance value is not reliable and maybe should not
                    # be considered as a replacement value
                    p_missing = p_missing or _type == SymPowerType.P_ZERO
                    q_missing = q_missing or _type == SymPowerType.Q_ZERO
        return p, q, p_missing, q_missing

    def _get_sensor_value(self, sensor):
        if sensor is None:
            return np.nan, np.nan, None
        id_ = sensor["id"]

        info = self._extra_info.get(id_, {})
        type_ = info.get("_type", None)

        p_ = sensor["p_measured"]
        q_ = sensor["q_measured"]
        return p_, q_, type_

    def component_name(self) -> ComponentType:
        return ComponentType.sym_power_sensor

    def _print_node(self, node_id):
        topo_node = self._topo[node_id]

        branches_at_node = topo_node.get("_branches")
        if branches_at_node is not None:
            for branch in branches_at_node:
                self._print_branch(branch)

        for component_type in [
            ComponentType.sym_gen,
            ComponentType.sym_load,
            ComponentType.shunt,
        ]:
            components = topo_node.get(component_type)
            if components is None:
                continue
            for component in components:
                self.print_appliance(component)

    def _print_branch(self, branch_id):
        tb = self._topo[branch_id]
        tp_type = tb["_extra"]["_type"]
        p_from, q_from, from_type = self._get_sensor_value(tb.get("_sensor_p_from"))
        p_from_str = print_num("p_from", p_from, from_type == SymPowerType.P_ZERO)
        q_from_str = print_num("q_from", q_from, from_type == SymPowerType.Q_ZERO)
        str_ = f"\t\t{tp_type:25} id={branch_id:>5} name={self._id_mapping.get_name_from_pgm(branch_id):<32}: {p_from_str} {q_from_str} {from_type}"
        log_ddd(str_)

        p_to, q_to, to_type = self._get_sensor_value(tb.get("_sensor_p_to"))
        p_to_str = print_num("p_to  ", p_to, to_type == SymPowerType.P_ZERO)
        q_to_str = print_num("q_to  ", q_to, to_type == SymPowerType.Q_ZERO)
        str_ = f"\t\t{'':25}    {'':5}      {'':32}  {p_to_str} {q_to_str} {to_type}"
        log_ddd(str_)

    def print_appliance(self, appliance_id):
        ts = self._topo[appliance_id]
        ts_type = ts["_extra"]["_type"]
        p, q, type_ = self._get_sensor_value(ts.get("_sensor_p"))
        p_str = print_num("p     ", p, type_ == SymPowerType.P_ZERO)
        q_str = print_num("q     ", q, type_ == SymPowerType.Q_ZERO)
        str_ = f"\t\t{ts_type:25} id={appliance_id:>5} name={self._id_mapping.get_name_from_pgm(appliance_id):<32}: {p_str} {q_str} {type_}"
        log_ddd(str_)


def print_num(prop, val, val_zero):
    return f"{prop}={val/1e6:10.3f} {is_zero(val_zero)}"


def is_zero(val):
    return "*" if val else " "
