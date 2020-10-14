from mmcomponents.components.blueprints.generic_component import GenericComponent
from mmelemental.models.util.output import FileOutput
from mmelemental.models.molecule.parmed_molecule import ParmedMolecule
from mmelemental.models.molecule.mol_reader import MoleculeReaderInput
from mmelemental.models.molecule.mm_molecule import Molecule
from typing import Dict, Any, List, Tuple, Optional

try:
    from parmed import structure, topologyobjects
except:
    raise ModuleNotFoundError('Make sure parmed is installed.')

class MoleculeToParmed(GenericComponent):
    """ A model for converting Molecule to ParmEd molecule object. """
    @classmethod
    def input(cls):
        return Molecule

    @classmethod
    def output(cls):
        return ParmedMolecule

    def execute(
        self,
        inputs: Dict[str, Any],
        extra_outfiles: Optional[List[str]] = None,
        extra_commands: Optional[List[str]] = None,
        scratch_name: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Tuple[bool, ParmedMolecule]:

        mmol = inputs
        pmol = structure.Structure()

        for index, symb in enumerate(mmol.symbols):

            name = mmol.names[index]
            atomic_number = mmol.atomic_numbers[index]
            mass = mmol.masses[index]

            # Will likely lose FF-related info ... but then Molecule is not supposed to store any params specific to FFs
            atom = topologyobjects.Atom(list=None, atomic_number=atomic_number, name=name, type=symb,
                 mass=mass, nb_idx=0, solvent_radius=0.0,
                 screen=0.0, tree='BLA', join=0.0, irotat=0.0, occupancy=1.0,
                 bfactor=0.0, altloc='', number=-1, rmin=None, epsilon=None,
                 rmin14=None, epsilon14=None)

            resname, resnum = mmol.residues[index]
            #classparmed.Residue(name, number=- 1, chain='', insertion_code='', segid='', list=None)[source]

            pmol.add_atom(atom, resname, resnum + 1, chain='', inscode='', segid='')

        for i, j , btype in mmol.connectivity:
            pmol.atoms[i].bond_to(pmol.atoms[j])

        pmol.coordinates = mmol.geometry

        print("Residues for ParmEd: ", pmol.residues[0].atoms)

        return True, ParmedMolecule(mol=pmol)

class ParmedToMolecule(GenericComponent):
    """ A model for converting ParmEd molecule to Molecule object. """

    @classmethod
    def input(cls):
        return MoleculeReaderInput

    @classmethod
    def output(cls):
        from mmelemental.models.molecule.mm_molecule import Molecule
        return Molecule

    def execute(
        self,
        inputs: Dict[str, Any],
        extra_outfiles: Optional[List[str]] = None,
        extra_commands: Optional[List[str]] = None,
        scratch_name: Optional[str] = None,
        timeout: Optional[int] = None) -> Tuple[bool, Dict[str, Any]]:
        
        from mmelemental.models.molecule.mm_molecule import Molecule

        if isinstance(inputs, dict):
            inputs = MoleculeReaderComponent.input()(**inputs)
        
        if inputs.data:
            dtype = inputs.data.dtype
            assert dtype == 'parmed'
            pmol = inputs.data
        elif inputs.code:
            raise NotImplementedError('ParmEd does not support instantiating molecule objects from chemical codes.')          
        elif inputs.file:
            dtype = inputs.file.ext
            from mmelemental.models.molecule.parmed_molecule import ParmedMolecule
            pmol = ParmedMolecule.build_mol(inputs, dtype)
        else:
            raise NotImplementedError(f'Data type {dtype} not yet supported.')
        
        if inputs.args:
            orient = inputs.args.get('orient')
            validate = inputs.args.get('validate')
            kwargs = inputs.args.get('kwargs')
        else:
            orient, validate, kwargs = False, None, None

        symbs = [atom.element_name for atom in pmol.mol.atoms]
        names = [atom.name for atom in pmol.mol.atoms]

        try:
            masses = [atom.mass for atom in pmol.mol.atoms]
        except:
            masses = None

        try:
            residues = [(atom.residue.name, atom.residue.idx) for atom in pmol.mol.atoms]
        except:
            residues = None
            
        connectivity = []

        for bond in pmol.mol.bonds:
            connectivity.append((bond.atom1.idx, bond.atom2.idx, bond.order))

        geo = pmol.mol.coordinates

        input_dict = {'symbols': symbs, 
                      'geometry': geo, 
                      'residues': residues, 
                      'connectivity': connectivity,
                      'masses': masses,
                      'names': names}        

        if kwargs:
            input_dict.update(kwargs)

        if inputs.code:
            return True, Molecule(orient=orient, validate=validate, identifiers={dtype: inputs.code}, **input_dict)
        else:
            return True, Molecule(orient=orient, validate=validate, **input_dict)