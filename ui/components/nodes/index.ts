import JiraTriggerNode from "./JiraTriggerNode";
import CreateMrNode from "./CreateMrNode";
import PlanPatchNode from "./PlanPatchNode";
import CiWaitNode from "./CiWaitNode";
import DeployNode from "./DeployNode";
import QaNode from "./QaNode";

export const nodeTypesMap = {
    jiraTrigger: JiraTriggerNode,
    createMr: CreateMrNode,
    planPatch: PlanPatchNode,
    ciWait: CiWaitNode,
    deploy: DeployNode,
    qa: QaNode,
};
