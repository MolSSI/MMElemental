from mmic.components.blueprints.generic_component import GenericComponent
from mmelemental.models.util.output import FileOutput
from mmelemental.models.molecule.mol_reader import MolReaderInput
from mmelemental.models.molecule.rdkit_molecule import RDKitMolecule
from mmelemental.models.molecule.mm_molecule import Molecule
from mmelemental.models.molecule.rdkit_molecule import Bond
from typing import Dict, Any, List, Tuple, Optional

try:
    from rdkit import Chem
except:
    raise ModuleNotFoundError('Make sure rdkit is installed.')

class MoleculeToRDKit(GenericComponent):
    """ A component for converting Molecule to RDKIT molecule object. """

    @classmethod
    def input(cls):
        return Molecule

    @classmethod
    def output(cls):
        return RDKitMolecule

    def execute(
        self,
        inputs: Dict[str, Any],
        extra_outfiles: Optional[List[str]] = None,
        extra_commands: Optional[List[str]] = None,
        scratch_name: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> Tuple[bool, RDKitMolecule]:

        rdkmol = Chem.Mol()
        erdkmol = Chem.EditableMol(rdkmol)
        mmol = inputs

        for index, symb in enumerate(mmol.symbols):
            atom = Chem.Atom(symb)
            resname, resnum = mmol.residues[index]
            name = mmol.names[index]

            if len(name) != 4: # For writing to PDB files, rdkit needs the len(name) to be exactly 4.
                if len(name) == 1:
                    name = ' ' + name + '  '
                elif len(name) == 2:
                    name = ' ' + name + ' '
                elif len(name) == 3:
                    name = ' ' + name

            residue = Chem.AtomPDBResidueInfo()
            residue.SetResidueName(resname)
            residue.SetName(name)
            residue.SetResidueNumber(resnum)
            residue.SetOccupancy(1.0)
            residue.SetTempFactor(0.0)
            atom.SetMonomerInfo(residue)
            erdkmol.AddAtom(atom)

        for i, j, btype in mmol.connectivity:
            erdkmol.AddBond(i, j, Bond.orders[int(btype)])            

        newmmol = erdkmol.GetMol()
        conf = Chem.Conformer(len(mmol.geometry))
        for i, coords in enumerate(mmol.geometry):
            conf.SetAtomPosition(i, coords)
        newmmol.AddConformer(conf)

        return True, RDKitMolecule(mol=newmmol)

class RDKitToMolecule(GenericComponent):
    """ A model for converting RDKIT molecule to Molecule object. """

    @classmethod
    def input(cls):
        return MolReaderInput

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
            inputs = MolReaderComponent.input()(**inputs)
        
        if inputs.data:
            dtype = inputs.data.dtype
            assert dtype == 'rdkit'
            rdmol = inputs.data
        elif inputs.code:
            dtype = inputs.code.code_type.lower()
            from mmelemental.models.molecule.rdkit_molecule import RDKitMolecule
            rdmol = RDKitMolecule.build(inputs, dtype)            
        elif inputs.file:
            dtype = inputs.file.ext
            from mmelemental.models.molecule.rdkit_molecule import RDKitMolecule
            rdmol = RDKitMolecule.build(inputs, dtype)
        else:
            raise NotImplementedError
        
        from mmelemental.models.molecule.rdkit_molecule import Bond

        if inputs.args:
            orient = inputs.args.get('orient')
            validate = inputs.args.get('validate')
            kwargs = inputs.args.get('kwargs')
        else:
            orient, validate, kwargs = False, None, None

        symbs = [atom.GetSymbol() for atom in rdmol.mol.GetAtoms()]

        try:
            residues = [(atom.GetPDBResidueInfo().GetResidueName(), 
                        atom.GetPDBResidueInfo().GetResidueNumber()) 
                        for atom in rdmol.mol.GetAtoms()]
            names = [atom.GetPDBResidueInfo().GetName() for atom in rdmol.mol.GetAtoms()]
        except:
            residues = None
            names = None
        
        connectivity = []

        for bond in rdmol.mol.GetBonds():
            bondOrder = Bond.orders.index(bond.GetBondType())
            connectivity.append((bond.GetBeginAtomIdx(), bond.GetEndAtomIdx(), 1)) # replace 1 with bondOrder, 
            # for now this is a hack for qcelemental does not allow bond orders higher than 5

        # Get any random conformer?
        geo = rdmol.mol.GetConformer(0).GetPositions()

        input_dict = {'symbols': symbs, 
                      'geometry': geo, 
                      'residues': residues, 
                      'connectivity': connectivity,
                      'names': names}        

        if kwargs:
            input_dict.update(kwargs)

        if inputs.code:
            return True, Molecule(orient=orient, validate=validate, identifiers={dtype: inputs.code}, **input_dict)
        else:
            return True, Molecule(orient=orient, validate=validate, **input_dict)
