import os
import sys
from dotenv import load_dotenv
sys.path.insert(1, os.path.abspath("./3-ML-Ops/util"))  # NOQA: E402
from workspace import get_workspace
from azureml.core import Model
from azureml.core.model import InferenceConfig
from azureml.core.webservice import AciWebservice, Webservice


def main():
    load_dotenv()
    workspace_name = os.environ.get("WS_NAME")
    resource_group = os.environ.get("RG_NAME")
    subscription_id = os.environ.get("SUBSCRIPTION_ID")
    tenant_id = os.environ.get("TENANT_ID")
    app_id = os.environ.get("SP_APP_ID")
    app_secret = os.environ.get("SP_APP_SECRET")
    model_name = os.environ.get("MODEL_NAME")
    inference_config_file = os.environ.get("INFERENCE_CONFIG")
    deployment_aci_config = os.environ.get("DEPLOYMENT_ACI_CONFIG")
    conda_dep_yml = os.environ.get("CONDA_DEPENDENCIES")
    score_path = os.environ.get("SCORE_PATH")
    score_source_dir = os.environ.get("SCORE_SOURCE_DIR")
    aci_service_name = os.environ.get("SERVICE_NAME") 


    # Get Azure machine learning workspace
    aml_workspace = get_workspace(
        workspace_name,
        resource_group,
        subscription_id,
        tenant_id,
        app_id,
        app_secret)

    inference_config = InferenceConfig(source_directory=score_source_dir,
                                    runtime= "python", 
                                    entry_script=score_path,
                                    conda_file=conda_dep_yml 
                                  )

    aciconfig = AciWebservice.deploy_configuration(cpu_cores=2, 
                                                memory_gb=4, 
                                                tags={"model": "BERT",  "method" : "tensorflow"}, 
                                                description='Predict StackoverFlow tags with BERT')
    
    model = aml_workspace.models[model_name]    

    aci_service = Model.deploy(aml_workspace, aci_service_name, [model], inference_config, aciconfig, overwrite=True)

    aci_service.wait_for_deployment(True)

    print(aci_service.state)

if __name__ == '__main__':
    main()