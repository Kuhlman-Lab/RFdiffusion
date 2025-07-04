import sys
import numpy as np
import random


class ContigMap:
    """
    Class for doing mapping.
    Inherited from Inpainting. To update at some point.
    Supports multichain or multiple crops from a single receptor chain.
    Also supports indexing jump (+200) or not, based on contig input.
    Default chain outputs are inpainted chains as A (and B, C etc if multiple chains), and all fragments of receptor chain on the next one (generally B)
    Output chains can be specified. Sequence must be the same number of elements as in contig string
    """

    def __init__(
        self,
        parsed_pdb,
        contigs=None,
        inpaint_seq=None,
        inpaint_str=None,
        length=None,
        ref_idx=None,
        hal_idx=None,
        idx_rf=None,
        inpaint_seq_tensor=None,
        inpaint_str_tensor=None,
        topo=False,
        provide_seq=None,
        inpaint_str_strand=None,
        inpaint_str_helix=None,
        inpaint_str_loop=None,
        sym_order=None,
    ):
        # sanity checks
        if contigs is None and ref_idx is None:
            sys.exit("Must either specify a contig string or precise mapping")
        if idx_rf is not None or hal_idx is not None or ref_idx is not None:
            if idx_rf is None or hal_idx is None or ref_idx is None:
                sys.exit(
                    "If you're specifying specific contig mappings, the reference and output positions must be specified, AND the indexing for RoseTTAFold (idx_rf)"
                )

        self.chain_order = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if length is not None:
            if "-" not in length:
                self.length = [int(length), int(length) + 1]
            else:
                self.length = [int(length.split("-")[0]), int(length.split("-")[1]) + 1]
        else:
            self.length = None
        self.ref_idx = ref_idx
        self.hal_idx = hal_idx
        self.idx_rf = idx_rf

        parse_inpaint = lambda x: "/".join(x).split("/") if x is not None else None
        self.inpaint_seq = parse_inpaint(inpaint_seq)
        self.inpaint_str = parse_inpaint(inpaint_str)

        self.inpaint_str_helix=parse_inpaint(inpaint_str_helix)
        self.inpaint_str_strand=parse_inpaint(inpaint_str_strand)
        self.inpaint_str_loop=parse_inpaint(inpaint_str_loop)

        self.inpaint_seq_tensor = inpaint_seq_tensor
        self.inpaint_str_tensor = inpaint_str_tensor
        self.parsed_pdb = parsed_pdb
        self.topo = topo
        self.sym_order = sym_order
        if ref_idx is None:
            # using default contig generation, which outputs in rosetta-like format
            self.contigs = contigs
            (
                self.sampled_mask,
                self.contig_length,
                self.n_inpaint_chains,
            ) = self.get_sampled_mask()
            self.receptor_chain = self.chain_order[self.n_inpaint_chains]
            (
                self.receptor,
                self.receptor_hal,
                self.receptor_rf,
                self.inpaint,
                self.inpaint_hal,
                self.inpaint_rf,
            ) = self.expand_sampled_mask()
            self.ref = self.inpaint + self.receptor
            self.hal = self.inpaint_hal + self.receptor_hal
            self.rf = self.inpaint_rf + self.receptor_rf
        else:
            # specifying precise mappings
            self.ref = ref_idx
            self.hal = hal_idx
            self.rf = idx_rf
        self.mask_1d = [False if i == ("_", "_") else True for i in self.ref]
        # take care of sequence and structure masking
        if self.inpaint_seq_tensor is None:
            if self.inpaint_seq is not None:
                self.inpaint_seq = self.get_inpaint_seq_str(self.inpaint_seq)
            else:
                self.inpaint_seq = np.array(
                    [True if i != ("_", "_") else False for i in self.ref]
                )
        else:
            self.inpaint_seq = self.inpaint_seq_tensor

        if self.inpaint_str_tensor is None:
            if self.inpaint_str is not None:
                self.inpaint_str = self.get_inpaint_seq_str(self.inpaint_str)
            else:
                self.inpaint_str = np.array(
                    [True if i != ("_", "_") else False for i in self.ref]
                )
        else:
            self.inpaint_str = self.inpaint_str_tensor
        # get 0-indexed input/output (for trb file)
        (
            self.ref_idx0,
            self.hal_idx0,
            self.ref_idx0_inpaint,
            self.hal_idx0_inpaint,
            self.ref_idx0_receptor,
            self.hal_idx0_receptor,
        ) = self.get_idx0()
        self.con_ref_pdb_idx = [i for i in self.ref if i != ("_", "_")]

        # Handle provide seq. This is zero-indexed, and used only for partial diffusion
        if provide_seq is not None:
            if type(provide_seq) == str:
                provide_seq = provide_seq.split(",")
            for i in provide_seq:
                if "-" in i:
                    self.inpaint_seq[
                        int(i.split("-")[0]) : int(i.split("-")[1]) + 1
                    ] = True
                else:
                    self.inpaint_seq[int(i)] = True

        """
        We have now added the ability to specify the secondary structure of provided sequence.
        This is described in Liu et al., 2024
        https://www.biorxiv.org/content/10.1101/2024.07.16.603789v1
        This is for the case that e.g. you have a sequence, but don't know the structure (like an IDR), but
        want to specify the secondary structure of this sequence.
        Making this compatible with the contigmap object allows all the variable length stuff to be handled.
        
        The logic:
        Secondary structure is provided at the command line, using the following three flags:
            inpaint_str_helix
            inpaint_str_strand
            inpaint_str_loop
        
        These are so named because they pertain to the region of the input pdb that you have applied inpaint_str to
        In other words, any part of the input protein you are masking the structure of, you can specify the secondary structure of.
        However, you can't specify the secondary structure of a region you're not applying inpaint_str to, as this doesn't make sense.
        """

        if any(x is not None for x in (inpaint_str_helix, inpaint_str_strand, inpaint_str_loop)):
            self.ss_spec={}
            order=['helix','strand','loop']
            for idx, i in enumerate([inpaint_str_helix, inpaint_str_strand, inpaint_str_loop]):
                if i is not None:
                    self.ss_spec[order[idx]] = ~self.get_inpaint_seq_str(i, ss=True)
                else:
                    self.ss_spec[order[idx]] = np.zeros(len(self.inpaint_seq), dtype=bool)
            # some sensible checks
            for key, mask in self.ss_spec.items():
                assert sum(mask*self.inpaint_str) == 0, f"You've specified {key} residues that are not structure-masked with inpaint_str. This doesn't really make sense."
            stack=np.vstack([mask for mask in self.ss_spec.values()])
            assert np.max(np.sum(stack, axis=0)) == 1, "You've given multiple secondary structure assignations to an input residue. This doesn't make sense."

    def get_sampled_mask(self):
        """
        Function to get a sampled mask from a contig.
        """
        length_compatible = False
        count = 0
        while length_compatible is False:
            inpaint_chains = 0
            contig_list = self.contigs[0].strip().split()
            if self.sym_order:
                assert len(contig_list) in [1, self.sym_order], "Number of chains in contig must be 1 or match symmetry order"

                if len(contig_list) == self.sym_order:
                    # Verify that all contigs are the same
                    ref_contigs = contig_list.copy()
                    for i in range(len(ref_contigs)):
                        subcons = ref_contigs[i].split("/")
                        for j in range(len(subcons)):
                            if subcons[j][0].isalpha():
                                if "-" in subcons[j]:
                                    subcons[j] = str(
                                        int(subcons[j][1:].split("-")[1])
                                        - int(subcons[j][1:].split("-")[0])
                                        + 1
                                    )
                                else:
                                    subcons[j] = "1"
                        ref_contigs[i] = "/".join(subcons)
                    for i in range(1, len(ref_contigs)):
                        assert ref_contigs[i] == ref_contigs[0], "All contigs must be the same structure when using multiple chains and symmetry"
                    og_contigs = contig_list.copy()
                    contig_list = [contig_list[0]]
                    check_symmetry = False
                else:
                    check_symmetry = True
            else:
                check_symmetry = False

            sampled_mask = []
            sampled_mask_length = 0
            # allow receptor chain to be last in contig string
            if all([i[0].isalpha() for i in contig_list[-1].split("/")]):
                contig_list[-1] = f"{contig_list[-1]}/0"
            for con in contig_list:
                if (
                    all([i[0].isalpha() for i in con.split("/")[:-1]])
                    and con.split("/")[-1] == "0"
                ) or self.topo is True:
                    # receptor chain
                    sampled_mask.append(con)
                else:
                    inpaint_chains += 1
                    # chain to be inpainted. These are the only chains that count towards the length of the contig
                    subcons = con.split("/")
                    subcon_out = []
                    for subcon in subcons:
                        if subcon[0].isalpha():
                            subcon_out.append(subcon)
                            if "-" in subcon:
                                sampled_mask_length += (
                                    int(subcon.split("-")[1])
                                    - int(subcon.split("-")[0][1:])
                                    + 1
                                )
                            else:
                                sampled_mask_length += 1

                        else:
                            if "-" in subcon:
                                length_inpaint = random.randint(
                                    int(subcon.split("-")[0]), int(subcon.split("-")[1])
                                )
                                subcon_out.append(f"{length_inpaint}-{length_inpaint}")
                                sampled_mask_length += length_inpaint
                            elif subcon == "0":
                                subcon_out.append("0")
                            else:
                                length_inpaint = int(subcon)
                                subcon_out.append(f"{length_inpaint}-{length_inpaint}")
                                sampled_mask_length += int(subcon)
                    sampled_mask.append("/".join(subcon_out))
            # check length is compatible
            if self.length is not None:
                if (
                    sampled_mask_length >= self.length[0]
                    and sampled_mask_length < self.length[1]
                ):
                    length_compatible = True
            else:
                length_compatible = True

            # check if length works with symmetry
            if length_compatible and check_symmetry:
                if sampled_mask_length % self.sym_order != 0:
                    length_compatible = False

            count += 1
            if count == 100000:  # contig string incompatible with this length
                if self.length is not None and self.sym_order is not None:
                    sys.exit(
                        "Contig string incompatible with length range and symmetry order"
                    )
                elif self.length is not None:
                    sys.exit("Contig string incompatible with --length range")
                elif self.sym_order is not None:
                    sys.exit("Contig string incompatible with symmetry order")
                else:
                    sys.exit("Unable to generate combatible contig")
                
        # Rebuild values when using symmetry and multiple chains
        if self.sym_order is not None and check_symmetry is False:
            sampled_mask = sampled_mask * self.sym_order
            sampled_mask_length = sampled_mask_length * self.sym_order
            inpaint_chains = inpaint_chains * self.sym_order
            for i, (ref_contig, sampled_contig) in enumerate(zip(og_contigs, sampled_mask)):
                ref_subcons = ref_contig.split("/")
                sampled_subcons = sampled_contig.split("/")
                for j in range(len(ref_subcons)):
                    if ref_subcons[j][0].isalpha():
                        sampled_subcons[j] = ref_subcons[j]
                sampled_mask[i] = "/".join(sampled_subcons)
        return sampled_mask, sampled_mask_length, inpaint_chains

    def expand_sampled_mask(self):
        chain_order = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        receptor = []
        inpaint = []
        receptor_hal = []
        inpaint_hal = []
        receptor_idx = 1
        inpaint_idx = 1
        inpaint_chain_idx = -1
        receptor_chain_break = []
        inpaint_chain_break = []
        for con in self.sampled_mask:
            if (
                all([i[0].isalpha() for i in con.split("/")[:-1]])
                and con.split("/")[-1] == "0"
            ) or self.topo is True:
                # receptor chain
                subcons = con.split("/")[:-1]
                assert all(
                    [i[0] == subcons[0][0] for i in subcons]
                ), "If specifying fragmented receptor in a single block of the contig string, they MUST derive from the same chain"
                assert all(
                    int(subcons[i].split("-")[0][1:])
                    < int(subcons[i + 1].split("-")[0][1:])
                    for i in range(len(subcons) - 1)
                ), "If specifying multiple fragments from the same chain, pdb indices must be in ascending order!"
                for idx, subcon in enumerate(subcons):
                    ref_to_add = [
                        (subcon[0], i)
                        for i in np.arange(
                            int(subcon.split("-")[0][1:]), int(subcon.split("-")[1]) + 1
                        )
                    ]
                    receptor.extend(ref_to_add)
                    receptor_hal.extend(
                        [
                            (self.receptor_chain, i)
                            for i in np.arange(
                                receptor_idx, receptor_idx + len(ref_to_add)
                            )
                        ]
                    )
                    receptor_idx += len(ref_to_add)
                    if idx != len(subcons) - 1:
                        idx_jump = (
                            int(subcons[idx + 1].split("-")[0][1:])
                            - int(subcon.split("-")[1])
                            - 1
                        )
                        receptor_chain_break.append(
                            (receptor_idx - 1, idx_jump)
                        )  # actual chain break in pdb chain
                    else:
                        receptor_chain_break.append(
                            (receptor_idx - 1, 200)
                        )  # 200 aa chain break
            else:
                inpaint_chain_idx += 1
                for subcon in con.split("/"):
                    if subcon[0].isalpha():
                        ref_to_add = [
                            (subcon[0], i)
                            for i in np.arange(
                                int(subcon.split("-")[0][1:]),
                                int(subcon.split("-")[1]) + 1,
                            )
                        ]
                        inpaint.extend(ref_to_add)
                        inpaint_hal.extend(
                            [
                                (chain_order[inpaint_chain_idx], i)
                                for i in np.arange(
                                    inpaint_idx, inpaint_idx + len(ref_to_add)
                                )
                            ]
                        )
                        inpaint_idx += len(ref_to_add)

                    else:
                        inpaint.extend([("_", "_")] * int(subcon.split("-")[0]))
                        inpaint_hal.extend(
                            [
                                (chain_order[inpaint_chain_idx], i)
                                for i in np.arange(
                                    inpaint_idx, inpaint_idx + int(subcon.split("-")[0])
                                )
                            ]
                        )
                        inpaint_idx += int(subcon.split("-")[0])
                inpaint_chain_break.append((inpaint_idx - 1, 200))

        if self.topo is True or inpaint_hal == []:
            receptor_hal = [(i[0], i[1]) for i in receptor_hal]
        else:
            receptor_hal = [
                (i[0], i[1] + inpaint_hal[-1][1]) for i in receptor_hal
            ]  # rosetta-like numbering
        # get rf indexes, with chain breaks
        inpaint_rf = np.arange(0, len(inpaint))
        receptor_rf = np.arange(len(inpaint) + 200, len(inpaint) + len(receptor) + 200)
        for ch_break in inpaint_chain_break[:-1]:
            receptor_rf[:] += 200
            inpaint_rf[ch_break[0] :] += ch_break[1]
        for ch_break in receptor_chain_break[:-1]:
            receptor_rf[ch_break[0] :] += ch_break[1]

        return (
            receptor,
            receptor_hal,
            receptor_rf.tolist(),
            inpaint,
            inpaint_hal,
            inpaint_rf.tolist(),
        )

    def get_inpaint_seq_str(self, inpaint_s, ss=False):
        '''
        function to generate inpaint_str or inpaint_seq masks specific to this contig
        '''
        if not ss:
            s_mask = np.copy(self.mask_1d)
        else:
            s_mask= np.ones(len(self.mask_1d), dtype=bool)
        inpaint_s_list = []
        for i in inpaint_s:
            if "-" in i:
                inpaint_s_list.extend(
                    [
                        (i[0], p)
                        for p in range(
                            int(i.split("-")[0][1:]), int(i.split("-")[1]) + 1
                        )
                    ]
                )
            else:
                inpaint_s_list.append((i[0], int(i[1:])))
        for res in inpaint_s_list:
            if res in self.ref:
                s_mask[self.ref.index(res)] = False  # mask this residue

        return np.array(s_mask)

    def get_idx0(self):
        ref_idx0 = []
        hal_idx0 = []
        ref_idx0_inpaint = []
        hal_idx0_inpaint = []
        ref_idx0_receptor = []
        hal_idx0_receptor = []
        for idx, val in enumerate(self.ref):
            if val != ("_", "_"):
                assert val in self.parsed_pdb["pdb_idx"], f"{val} is not in pdb file!"
                hal_idx0.append(idx)
                ref_idx0.append(self.parsed_pdb["pdb_idx"].index(val))
        for idx, val in enumerate(self.inpaint):
            if val != ("_", "_"):
                hal_idx0_inpaint.append(idx)
                ref_idx0_inpaint.append(self.parsed_pdb["pdb_idx"].index(val))
        for idx, val in enumerate(self.receptor):
            if val != ("_", "_"):
                hal_idx0_receptor.append(idx)
                ref_idx0_receptor.append(self.parsed_pdb["pdb_idx"].index(val))

        return (
            ref_idx0,
            hal_idx0,
            ref_idx0_inpaint,
            hal_idx0_inpaint,
            ref_idx0_receptor,
            hal_idx0_receptor,
        )

    def get_mappings(self):
        mappings = {}
        mappings["con_ref_pdb_idx"] = [i for i in self.inpaint if i != ("_", "_")]
        mappings["con_hal_pdb_idx"] = [
            self.inpaint_hal[i]
            for i in range(len(self.inpaint_hal))
            if self.inpaint[i] != ("_", "_")
        ]
        mappings["con_ref_idx0"] = np.array(self.ref_idx0_inpaint)
        mappings["con_hal_idx0"] = np.array(self.hal_idx0_inpaint)
        if self.inpaint != self.ref:
            mappings["complex_con_ref_pdb_idx"] = [
                i for i in self.ref if i != ("_", "_")
            ]
            mappings["complex_con_hal_pdb_idx"] = [
                self.hal[i] for i in range(len(self.hal)) if self.ref[i] != ("_", "_")
            ]
            mappings["receptor_con_ref_pdb_idx"] = [
                i for i in self.receptor if i != ("_", "_")
            ]
            mappings["receptor_con_hal_pdb_idx"] = [
                self.receptor_hal[i]
                for i in range(len(self.receptor_hal))
                if self.receptor[i] != ("_", "_")
            ]
            mappings["complex_con_ref_idx0"] = np.array(self.ref_idx0)
            mappings["complex_con_hal_idx0"] = np.array(self.hal_idx0)
            mappings["receptor_con_ref_idx0"] = np.array(self.ref_idx0_receptor)
            mappings["receptor_con_hal_idx0"] = np.array(self.hal_idx0_receptor)
        mappings["inpaint_str"] = self.inpaint_str
        mappings["inpaint_seq"] = self.inpaint_seq
        mappings["sampled_mask"] = self.sampled_mask
        mappings["mask_1d"] = self.mask_1d
        return mappings
