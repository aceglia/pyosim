"""
Analyze tool class in pyosim.
Used in static optimization, muscle analysis and joint reaction analysis.
"""
from pathlib import Path
import numpy as np
import opensim as osim


class AnalyzeTool:
    """
    Analyze tool in pyosim.
    Used in static optimization, muscle analysis and joint reaction analysis.

    Parameters
    ----------
    model_input : str
        Path to the osim model
    xml_input : str
        Path to the generic so xml
    xml_output : str
        Output path of the so xml
    xml_forces : str, optional
        Path to the generic forces sensor xml (Optional)
    ext_forces_dir : str, optional
        Path of the directory containing the external forces files (`.sto`) (Optional)
    muscle_forces_dir : str, optional
        Path of the directory containing the muscle forces files (`.sto`) (Optional)
    mot_files : str, Path, list
        Path or list of path to the directory containing the motion files (`.mot`)
    sto_output : Path, str
        Output directory
    xml_actuators: Path, str
        Actuators (Optional)
    prefix : str, optional
        Optional prefix to put in front of the output filename (typically model name) (Optional)
    low_pass : int, optional
        Cutoff frequency for an optional low pass filter on coordinates (Optional)
    remove_empty_files : bool, optional
        remove empty files i in `sto_output` if True (Optional)
    multi : bool, optional
        Launch AnalyzeTool in multiprocessing if True

    Examples
    --------
    >>> from pathlib import Path
    >>>
    >>> from pyosim import AnalyzeTool
    >>>
    >>> PROJECT_PATH = Path('../Misc/project_sample')
    >>> TEMPLATES_PATH = PROJECT_PATH / '_templates'
    >>>
    >>> participant = 'dapo'
    >>> model = 'wu'
    >>> trials = [ifile for ifile in (PROJECT_PATH / participant / '1_inverse_kinematic').glob('*.mot')]
    >>>
    >>> path_kwargs = {
    >>>     'model_input': f"{(PROJECT_PATH / participant / '_models' / model).resolve()}_scaled_markers.osim",
    >>>     'xml_input': f"{(TEMPLATES_PATH / model).resolve()}_so.xml",
    >>>     'xml_output': f"{(PROJECT_PATH / participant / '_xml' / model).resolve()}_so.xml",
    >>>     'xml_forces': f"{(TEMPLATES_PATH / 'forces_sensor.xml').resolve()}",
    >>>     'xml_actuators': f"{(TEMPLATES_PATH / f'{model}_actuators.xml').resolve()}",
    >>>     'ext_forces_dir': f"{(PROJECT_PATH / participant / '0_forces').resolve()}",
    >>>     'muscle_forces_dir': f"{(PROJECT_PATH / participant / '3_static_optimization').resolve()}",
    >>>     'sto_output': f"{(PROJECT_PATH / participant / '3_static_optimization').resolve()}",
    >>> }
    >>>
    >>> AnalyzeTool(
    >>>     **path_kwargs,
    >>>     mot_files=trials,
    >>>     prefix=model,
    >>>     low_pass=5
    >>> )
    """

    def __init__(
        self,
        model_input,
        xml_input,
        xml_output,
        sto_output,
        mot_files,
        forces_file=None,
        xml_forces=None,
        ext_forces_dir=None,
        muscle_forces_dir=None,
        xml_actuators=None,
        prefix=None,
        low_pass=None,
        remove_empty_files=False,
        multi=False,
        contains=None,
        print_to_xml=False,
        time_range=None,
    ):
        self.model_input = model_input
        self.xml_input = xml_input
        self.xml_output = xml_output
        self.sto_output = sto_output
        self.xml_forces = xml_forces
        self.forces_file = forces_file
        self.ext_forces_dir = ext_forces_dir
        self.muscle_forces_dir = muscle_forces_dir
        self.xml_actuators = xml_actuators
        self.prefix = prefix
        self.low_pass = low_pass
        self.remove_empty_files = remove_empty_files
        self.multi = multi
        self.contains = contains
        self.print_to_xml = print_to_xml
        if isinstance(time_range, (list, np.ndarray)):
            self.start_time = time_range[0]
            self.end_time = time_range[1]
        elif time_range is None:
            self.start_time, self.end_time = None, None
        else:
            raise RuntimeError("Time range must be a list or an array of start and last time frame.")

        if not isinstance(mot_files, list):
            self.mot_files = [mot_files]
        else:
            self.mot_files = mot_files

        if not isinstance(self.mot_files[0], Path):
            self.mot_files = [Path(i) for i in self.mot_files]

        self.main_loop()

    def main_loop(self):
        if self.multi:
            import os
            from multiprocessing import Pool

            pool = Pool(os.cpu_count())
            pool.map(self.run_analyze_tool, self.mot_files)
        else:
            for itrial in self.mot_files:
                self.run_analyze_tool(itrial)

    def run_analyze_tool(self, trial):
        if self.prefix and not trial.stem.startswith(self.prefix):
            # skip file if user specified a prefix and prefix is not present in current file
            pass
        else:
            print(f"\t{trial.stem}")

            # model
            model = osim.Model(self.model_input) if isinstance(self.model_input, str) is True else self.model_input
            model.initSystem()

            # get starting and ending time
            motion = osim.Storage(f"{trial.resolve()}")
            if self.start_time and self.start_time != -1:
                first_time = self.start_time
            else:
                first_time = motion.getFirstTime()
            if self.end_time and self.end_time != -1:
                last_time = self.end_time
            else:
                last_time = motion.getLastTime()

            # prepare external forces xml file
            if self.xml_forces:
                external_loads = osim.ExternalLoads(self.xml_forces, True)
                if self.prefix:
                    external_loads.setDataFileName(
                        f"{Path(self.ext_forces_dir, trial.stem.replace(f'{self.prefix}_', '')).resolve()}.sto"
                    )
                else:
                    external_loads.setDataFileName(
                        f"{Path(self.ext_forces_dir, trial.stem).resolve()}.sto"
                    )
                external_loads.setExternalLoadsModelKinematicsFileName(
                    f"{trial.resolve()}"
                )
                if self.low_pass:
                    external_loads.setLowpassCutoffFrequencyForLoadKinematics(
                        self.low_pass
                    )
                temp_xml = Path(f"{trial.stem}_temp.xml")
                external_loads.printToXML(f"{temp_xml.resolve()}")  # temporary xml file

            current_class = self.get_class_name()
            params = self.parse_analyze_set_xml(self.xml_input, node=current_class)
            solve_for_equilibrium = False
            if current_class == "StaticOptimization":
                analysis = osim.StaticOptimization(model)
                analysis.setUseModelForceSet(params["use_model_force_set"])
                analysis.setActivationExponent(params["activation_exponent"])
                analysis.setUseMusclePhysiology(params["use_muscle_physiology"])
                analysis.setConvergenceCriterion(
                    params["optimizer_convergence_criterion"]
                )
                analysis.setMaxIterations(int(params["optimizer_max_iterations"]))
            elif current_class == "MuscleAnalysis":
                solve_for_equilibrium = True
                analysis = osim.MuscleAnalysis(model)
                coord = osim.ArrayStr()
                for c in params["moment_arm_coordinate_list"]:
                    coord.append(c)
                analysis.setCoordinates(coord)

                mus = osim.ArrayStr()
                for m in params["muscle_list"]:
                    mus.append(m)
                analysis.setMuscles(mus)
                # analysis.setComputeMoments(params["compute_moments"])
            elif current_class == "JointReaction":
                # construct joint reaction analysis
                analysis = osim.JointReaction(model)
                if params["forces_file"] or self.forces_file:
                    force_file = self.forces_file if self.forces_file else params["forces_file"]
                    analysis.setForcesFileName(force_file)

                joint = osim.ArrayStr()
                for j in params["joint_names"]:
                    joint.append(j)
                analysis.setJointNames(joint)

                body = osim.ArrayStr()
                for b in params["apply_on_bodies"]:
                    body.append(b)
                analysis.setOnBody(body)

                frame = osim.ArrayStr()
                for f in params["express_in_frame"]:
                    frame.append(f)
                analysis.setInFrame(frame)
            else:
                raise ValueError("AnalyzeTool must be called from a child class")
            analysis.setModel(model)
            analysis.setName(current_class)
            analysis.setOn(params["on"])
            analysis.setStepInterval(int(params["step_interval"]))
            analysis.setInDegrees(params["in_degrees"])
            analysis.setStartTime(first_time)
            analysis.setEndTime(last_time)
            model.addAnalysis(analysis)

            if self.print_to_xml is True:
                analysis.printToXML(f"{self.xml_output}/{current_class}_analysis.xml")

            # analysis tool
            analyze_tool = osim.AnalyzeTool(model)
            analyze_tool.setName(trial.stem)
            analyze_tool.setModel(model)
            analyze_tool.setModelFilename(Path(model.toString()).stem)
            analyze_tool.setSolveForEquilibrium(solve_for_equilibrium)

            if self.xml_actuators:
                force_set = osim.ArrayStr()
                force_set.append(self.xml_actuators)
                analyze_tool.setForceSetFiles(force_set)
                analyze_tool.updateModelForces(model, self.xml_actuators)

            analyze_tool.setInitialTime(first_time)
            analyze_tool.setFinalTime(last_time)

            if self.low_pass:
                analyze_tool.setLowpassCutoffFrequency(self.low_pass)

            analyze_tool.setCoordinatesFileName(f"{trial.resolve()}")
            if self.xml_forces:
                analyze_tool.setExternalLoadsFileName(f"{temp_xml}")
            analyze_tool.setLoadModelAndInput(True)
            analyze_tool.setResultsDir(f"{self.sto_output}")

            analyze_tool.run()

            # Remove analysis
            model.removeAnalysis(analysis)

            if self.xml_forces:
                temp_xml.unlink()  # delete temporary xml file

            if self.remove_empty_files:
                self._remove_empty_files(directory=self.sto_output)

            if self.contains:
                self._subset_output(directory=self.sto_output, contains=self.contains)

    def parse_analyze_set_xml(self, filename, node):
        from xml.etree import ElementTree

        tree = ElementTree.parse(filename)
        root = tree.getroot()

        def isfloat(value):
            try:
                float(value)
                return True
            except ValueError:
                return False

        out = {}
        for t in root.findall(f".//{node}/*"):
            if t.text == "true":
                out.update({t.tag: True})
            elif t.text == "false":
                out.update({t.tag: False})
            elif t.text is None:
                out.update({t.tag: t.text})
            elif isfloat(t.text) is True:
                out.update({t.tag: float(t.text)})
            else:
                out.update({t.tag: self._str_to_list(t.text)})


        return out

    @staticmethod
    def _str_to_list(string):
        count = 0
        car = string[count]
        while car == " ":
            count += 1
            car = string[count]

        string = string[count:]
        li = list(string.split(" "))
        return li

    @staticmethod
    def _remove_empty_files(directory, threshold=1000):
        """
        Remove empty files from a directory.

        Parameters
        ----------
        directory : str, Path
            directory
        threshold : int
            threshold in bytes
        """
        for ifile in Path(directory).iterdir():
            if ifile.stat().st_size < threshold:
                ifile.unlink()

    @staticmethod
    def _subset_output(directory, contains):
        """
        Keep only files that contains `contains` string

        Parameters
        ----------
        directory : str, Path
            directory
        contains : str
            string
        """
        for ifile in Path(directory).iterdir():
            if contains not in ifile.stem:
                ifile.unlink()

    @classmethod
    def get_class_name(cls):
        return cls.__name__

