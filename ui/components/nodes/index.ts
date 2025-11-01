import JiraTriggerNode from "./JiraTriggerNode";
export const nodeTypesMap = {
    jiraTrigger: JiraTriggerNode,
    planPatch: JiraTriggerNode, // placeholder: reuse until custom nodes added
    createMR: JiraTriggerNode,
    ciWait: JiraTriggerNode,
    deploy: JiraTriggerNode,
    qa: JiraTriggerNode,
};
