from qgis.core import QgsProcessing
from qgis.core import QgsProcessingContext
import processing
from pathlib import Path

import sys

sys.path.append(Path(__file__).parents[1])
from qnspect_utils import perform_raster_math


def run_direct_and_percent_comparisons(
    scenario_dir_a: Path,
    scenario_dir_b: Path,
    output_dir: Path,
    name: str,  # ex: Lead Local
    feedback,
    context,
    outputs,
    load_outputs: bool,
):
    input_dict = {
        "band_a": 1,
        "band_b": 1,
        "input_a": str(scenario_dir_a / f"{name}.tif"),
        "input_b": str(scenario_dir_b / f"{name}.tif"),
    }
    _run_comparison_type(
        output_dir=output_dir,
        input_dict=input_dict,
        name=name,
        compare_type="Direct",
        expression="A - B",
        feedback=feedback,
        context=context,
        outputs=outputs,
        load_outputs=load_outputs,
    )
    _run_comparison_type(
        output_dir=output_dir,
        input_dict=input_dict,
        name=name,
        compare_type="Percent",
        expression="100 * ((A - B) / A)",
        feedback=feedback,
        context=context,
        outputs=outputs,
        load_outputs=load_outputs,
    )


def _run_comparison_type(
    output_dir: Path,
    input_dict: dict,
    name: str,  # ex: Lead Local
    compare_type: str,
    expression: str,
    feedback,
    context,
    outputs,
    load_outputs: bool,
):
    type_name = f"{name} {compare_type}"
    output = outputs[type_name] = perform_raster_math(
        exprs=expression,
        input_dict=input_dict,
        context=context,
        feedback=feedback,
        output=str(output_dir / f"{type_name}.tif"),
    )
    layer_name = f"{type_name} "
    if load_outputs:
        context.addLayerToLoadOnCompletion(
            output["OUTPUT"],
            QgsProcessingContext.LayerDetails(
                layer_name, context.project(), layer_name
            ),
        )
