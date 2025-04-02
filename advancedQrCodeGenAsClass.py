import qrcode
from tkinter import *
from tkinter import ttk, messagebox, colorchooser
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.svg import SvgImage
import os
from PIL import ImageTk, Image


class qrCodeGen:
    def __init__(self, root):
        """App for interactive creation of QR codes using qrcode and
        tkinter modules. Written for Python 3.7.7 and with qrcode
        version 7.3.1.
        """

        root.title("Advanced QR Code Generator by Jan Klíma")

        mainf = ttk.Frame(root, padding="5 5 5 10")
        mainf.grid(column=0, row=0)  # , sticky=(N, W, E, S)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        headingf = ttk.Frame(mainf, padding="5 5 5 5")
        headingf.grid(column=0, row=0, columnspan=8)
        heading = ttk.Label(headingf, text="Advanced QR Code Generator by Jan"
                            + " Klíma", font=("Courier", 20, "bold"))
        heading.grid(column=0, row=0)
        subtitle = ttk.Label(headingf, text="Written in Python 3.7.7 (3.10.8 "
                             + "tested) for qrcode module version 7.3.1.",
                             font=("Courier", 12))
        subtitle.grid(column=0, row=1, sticky=W)

        # declare variables
        self.pads = 5  # padding to all subframes
        self.mbt = "Advanced QR Code Generator"  # MessageBox Title
        self.mess = StringVar()  # entry text
        self.savedir = StringVar(value="")  # path where to save QR Code pic
        self.picname = StringVar()  # QR code pic name (without extension)
        self.collide = StringVar(value="ask")  # what to do in case of
        # ...colliding name of pic
        self.size = IntVar(value=1)  # size of the QR code standard
        self.errcor = StringVar(value="M")  # error correction standard
        self.ext = StringVar(value=".png")  # final pic extension
        self.embim = BooleanVar(value=False)  # embed an image in the center?
        self.embimp = StringVar()  # embedded image path
        self.bgcolor = StringVar(value="(255, 255, 255)")  # QR code background
        # ...color
        self.fcolor = StringVar(value="(0, 0, 0)")  # QR code face color
        self.boxsize = IntVar(value="10")  # box_size option in qrcode module
        self.bdsize = IntVar(value="5")  # border option in qrcode module
        self.boxstyle = StringVar(value="square")  # box style
        self.cmask = StringVar(value="solid")  # color_mask option in qrcode
        # ...module
        self.cmipath = StringVar()  # color mask image path
        self.color2 = StringVar(value="(0, 0, 255)")  # 2nd color for cmask
        self.presetname = StringVar()  # name of preset file to load/save,
        # ...without extension

        self.spvars = (self.mess, self.savedir, self.picname, self.collide,
                       self.size, self.errcor, self.ext, self.embim,
                       self.embimp, self.bgcolor, self.fcolor, self.boxsize,
                       self.bdsize, self.boxstyle, self.cmask, self.cmipath,
                       self.color2)  # SavedPresets VARiables
        self.spnames = ("mess", "savedir", "picname", "collide", "size",
                        "errcor", "ext", "embim", "embimp", "bgcolor",
                        "fcolor", "boxsize", "bdsize", "boxstyle", "cmask",
                        "cmipath", "color2")  # SavedPresets NAMES


        frame01 = ttk.Frame(mainf, padding=self.pads)
        frame01.grid(column=0, row=1, columnspan=4, sticky=W)
        mess_label = ttk.Label(frame01, text="Message/URL to encode:")
        mess_label.grid(column=0, row=0, sticky=W)
        mess_entry = ttk.Entry(frame01, width=50, textvariable=self.mess)
        mess_entry.grid(column=0, row=1, sticky=W)

        frame02 = ttk.Frame(mainf, padding=self.pads)
        frame02.grid(column=0, row=2, columnspan=4, sticky=W)
        savedir_label = ttk.Label(frame02, text="Location to save the QR code "
                                  + "at:")
        savedir_label.grid(column=0, row=0, sticky=W)
        savedir_entry = ttk.Entry(frame02, width=50, textvariable=self.savedir)
        savedir_entry.grid(column=0, row=1, sticky=W)

        frame03 = ttk.Frame(mainf, padding=self.pads)
        frame03.grid(column=0, row=3, columnspan=4, sticky=W)
        picname_label = ttk.Label(frame03, text="QR code name:")
        picname_label.grid(column=0, row=0, sticky=W)
        picname_coll = ttk.Label(frame03, text="On collision:")
        picname_coll.grid(column=1, row=0, sticky=E)
        picname_combo = ttk.Combobox(frame03, textvariable=self.collide,
                                     width=14,
                                     values=("ask", "overwrite",
                                             "warn & abort"))
        picname_combo.state(["readonly"])
        picname_combo.grid(column=2, row=0, sticky=E)
        picname_entry = ttk.Entry(frame03, width=50, textvariable=self.picname)
        picname_entry.grid(column=0, row=1, sticky=W, columnspan=3)

        frame04 = ttk.Frame(mainf, padding=self.pads)
        frame04.grid(column=0, row=4, columnspan=4, sticky=W)
        size_label = ttk.Label(frame04, text="Size standard from 1 to 40 (1 ~ "
                               + "21x21):")
        size_label.grid(column=0, row=0, sticky=W)
        size_entry = ttk.Entry(frame04, width=25, textvariable=self.size)
        size_entry.grid(column=0, row=1, sticky=W)

        frame05 = ttk.Frame(mainf, padding=self.pads)
        frame05.grid(column=0, row=5, columnspan=4, sticky=W)
        errcor_label = ttk.Label(frame05,
                                 text="Error correction standard/quality/can "
                                 + "recover:")
        errcor_label.grid(column=0, row=0, columnspan=2, sticky=W)
        ecl = ttk.Radiobutton(frame05, text="L/low/7%", variable=self.errcor,
                              value="L")
        ecl.grid(column=0, row=1, sticky=W)
        ecm = ttk.Radiobutton(frame05, text="M/medium/15%",
                              variable=self.errcor, value="M")
        ecm.grid(column=1, row=1, sticky=W)
        ecq = ttk.Radiobutton(frame05, text="Q/quite-high/25%",
                              variable=self.errcor, value="Q")
        ecq.grid(column=0, row=2, sticky=W)
        ech = ttk.Radiobutton(frame05, text="H/high/30%", variable=self.errcor,
                              value="H")
        ech.grid(column=1, row=2, sticky=W)

        frame06 = ttk.Frame(mainf, padding=self.pads)
        frame06.grid(column=0, row=6, columnspan=4, sticky=W)
        ext_label = ttk.Label(frame06, text="Image extension:")
        ext_label.grid(column=0, row=0, columnspan=2, sticky=W)
        extpng = ttk.Radiobutton(frame06, text="PNG", variable=self.ext,
                                 value=".png", command=self.optMngr0)
        extpng.grid(column=0, row=1, sticky=W)
        extsvg = ttk.Radiobutton(frame06, text="SVG (only Squared style "
                                 + "and B&W color)",
                                 variable=self.ext, value=".svg",
                                 command=self.optMngr0)
        extsvg.grid(column=1, row=1, sticky=W)

        frame07 = ttk.Frame(mainf, padding=self.pads)
        frame07.grid(column=0, row=7, columnspan=4, sticky=W)
        embim_check = ttk.Checkbutton(frame07, text="Embed a PNG image in the"
                                      + " center.", variable=self.embim,
                                      onvalue=True, offvalue=False,
                                      command=self.optMngr1)
        embim_check.grid(column=0, row=0, sticky=W, columnspan=2)
        embim_label = ttk.Label(frame07, text="   Path:")
        embim_label.grid(column=0, row=1, sticky=W)
        embim_entry = ttk.Entry(frame07, width=40, textvariable=self.embimp)
        embim_entry.grid(column=1, row=1, sticky=W)


        frame11 = ttk.Frame(mainf, padding=self.pads)
        frame11.grid(column=4, row=1, columnspan=4, sticky=W)
        bgcolor_label = ttk.Label(frame11, text="Background color (RGB "
                                  + "triplet, e.g. (255, 255, 255)):")
        bgcolor_label.grid(column=0, row=0, sticky=W, columnspan=2)
        bgcolor_entry = ttk.Entry(frame11, width=30, textvariable=self.bgcolor)
        bgcolor_entry.grid(column=0, row=1, sticky=W)
        bgcolor_selec = ttk.Button(frame11, text="See palette",
                                   command=self.gimmecolorbg)
        bgcolor_selec.grid(column=1, row=1, sticky=W)

        frame12 = ttk.Frame(mainf, padding=self.pads)
        frame12.grid(column=4, row=2, columnspan=4, sticky=W)
        fcolor_label = ttk.Label(frame12, text="Face color (RGB triplet, "
                                 + "e.g. (0, 0, 0)):")
        fcolor_label.grid(column=0, row=0, sticky=W, columnspan=2)
        fcolor_entry = ttk.Entry(frame12, width=30, textvariable=self.fcolor)
        fcolor_entry.grid(column=0, row=1, sticky=W)
        fcolor_selec = ttk.Button(frame12, text="See palette",
                                  command=self.gimmecolorf)
        fcolor_selec.grid(column=1, row=1, sticky=W)

        frame13 = ttk.Frame(mainf, padding=self.pads)
        frame13.grid(column=4, row=3, columnspan=4, sticky=W)
        boxsize_label = ttk.Label(frame13, text="Box size (pixels per each "
                                  + "'box' in the QR code):")
        boxsize_label.grid(column=0, row=0, sticky=W)
        boxsize_entry = ttk.Entry(frame13, width=25, textvariable=self.boxsize)
        boxsize_entry.grid(column=0, row=1, sticky=W)

        frame14 = ttk.Frame(mainf, padding=self.pads)
        frame14.grid(column=4, row=4, columnspan=4, sticky=W)
        bdsize_label = ttk.Label(frame14, text="Border size (in boxes, min. "
                                 + "is 4):")
        bdsize_label.grid(column=0, row=0, sticky=W)
        bdsize_entry = ttk.Entry(frame14, width=25, textvariable=self.bdsize)
        bdsize_entry.grid(column=0, row=1, sticky=W)

        frame15 = ttk.Frame(mainf, padding=self.pads)
        frame15.grid(column=4, row=5, columnspan=4, sticky=W)
        boxstyle_label = ttk.Label(frame15, text="Box style:")
        boxstyle_label.grid(column=0, row=0, sticky=W, columnspan=3)
        bss = ttk.Radiobutton(frame15, text="Square", variable=self.boxstyle,
                              value="square")
        bss.grid(column=0, row=1, sticky=W)
        bsgs = ttk.Radiobutton(frame15, text="Gapped square",
                               variable=self.boxstyle, value="gapsquare")
        bsgs.grid(column=1, row=1, sticky=W)
        bsvb = ttk.Radiobutton(frame15, text="Vertical bars",
                               variable=self.boxstyle, value="vbars")
        bsvb.grid(column=2, row=1, sticky=W)
        bsc = ttk.Radiobutton(frame15, text="Circle", variable=self.boxstyle,
                              value="circle")
        bsc.grid(column=0, row=2, sticky=W)
        bsr = ttk.Radiobutton(frame15, text="Rounded", variable=self.boxstyle,
                              value="rounded")
        bsr.grid(column=1, row=2, sticky=W)
        bshb = ttk.Radiobutton(frame15, text="Horizontal bars",
                               variable=self.boxstyle, value="hbars")
        bshb.grid(column=2, row=2, sticky=W)

        frame16 = ttk.Frame(mainf, padding=self.pads)
        frame16.grid(column=4, row=6, columnspan=4, sticky=W, rowspan=2)
        cmask_label = ttk.Label(frame16, text="Color mask:")
        cmask_label.grid(column=0, row=0, sticky=W, columnspan=3)
        cms = ttk.Radiobutton(frame16, text="Solid fill", variable=self.cmask,
                              value="solid", command=self.optMngr2)
        cms.grid(column=0, row=1, sticky=W)
        cmrg = ttk.Radiobutton(frame16, text="Radial gradient",
                               variable=self.cmask, value="rgrad",
                               command=self.optMngr2)
        cmrg.grid(column=1, row=1, sticky=W)
        cmsg = ttk.Radiobutton(frame16, text="Square gradient",
                               variable=self.cmask, value="sgrad",
                               command=self.optMngr2)
        cmsg.grid(column=2, row=1, sticky=W)
        cmhg = ttk.Radiobutton(frame16, text="Horizontal gradient",
                               variable=self.cmask, value="hgrad",
                               command=self.optMngr2)
        cmhg.grid(column=0, row=2, sticky=W)
        cmvg = ttk.Radiobutton(frame16, text="Vertical gradient",
                               variable=self.cmask, value="vgrad",
                               command=self.optMngr2)
        cmvg.grid(column=1, row=2, sticky=W)
        cmi = ttk.Radiobutton(frame16, text="Image (PNG)", variable=self.cmask,
                              value="image", command=self.optMngr2)
        cmi.grid(column=2, row=2, sticky=W)
        frame16s = ttk.Frame(frame16)
        frame16s.grid(column=0, row=3, sticky=W, columnspan=3)
        cmip_label = ttk.Label(frame16s, text="Image mask path:")
        cmip_label.grid(column=0, row=0, sticky=W)
        cmip_entry = ttk.Entry(frame16s, width=40, textvariable=self.cmipath)
        cmip_entry.grid(column=1, row=0, sticky=W)
        frame16s0 = ttk.Frame(frame16)
        frame16s0.grid(column=0, row=4, sticky=W, columnspan=3)
        color2_label = ttk.Label(frame16s0, text="2nd color (RGB triplet, e.g."
                                 + " (0, 0, 255)):")
        color2_label.grid(column=0, row=0, sticky=W)
        color2_entry = ttk.Entry(frame16s0, width=15, textvariable=self.color2)
        color2_entry.grid(column=1, row=0, sticky=W)
        color2_selec = ttk.Button(frame16s0, text="See palette",
                                  command=self.gimmecolor2)
        color2_selec.grid(column=2, row=0, sticky=W)


        frame20 = ttk.Frame(mainf, padding=self.pads)
        frame20.grid(column=0, row=10, columnspan=5, sticky=W)
        preset_label = ttk.Label(frame20, text="Presets:")
        preset_label.grid(column=0, row=0, sticky=W)
        preset_entry = ttk.Entry(frame20, width=20,
                                 textvariable=self.presetname)
        preset_entry.grid(column=1, row=0, sticky=W)
        preset_load = ttk.Button(frame20, text="Load", command=self.loadpresets)
        preset_load.grid(column=2, row=0, sticky=W, padx=5)
        preset_save = ttk.Button(frame20, text="Save", command=self.savepresets)
        preset_save.grid(column=3, row=0, sticky=W)
        preset_del = ttk.Button(frame20, text="Delete", command=self.delpresets)
        preset_del.grid(column=4, row=0, sticky=W, padx=5)
        # list of presets
        presli_label = ttk.Label(frame20, text="List of available presets:")
        presli_label.grid(column=0, row=1, columnspan=4, sticky=W)
        self.npres = os.listdir("presets/")
        self.presli_text = Text(frame20, width=20, height=len(self.npres))
        # ...needs to be preserved to rearrange
        self.presli_text.grid(column=0, row=2, columnspan=4, sticky=W, padx=5)
        for j in range(len(self.npres)):
            self.presli_text.insert("{}.0".format(j+1), self.npres[j][:-4]+"\n")
        self.presli_text['state'] = 'disabled'


        frame2 = ttk.Frame(mainf, padding=self.pads)
        frame2.grid(column=2, row=9, columnspan=4)
        butt = ttk.Button(frame2, text="Generate QR code (also Crtl+Enter)",
                          command=self.make)
        butt.grid(column=0, row=0, ipadx=10, ipady=5)
        butt_label = ttk.Label(frame2, text="*Please note that generating QR "
                               + "codes may take a while\n(max. few minutes) "
                               + "and the window may freeze.")
        butt_label.grid(column=0, row=1, sticky=W)


        self.svgrelatedwidgets = (bgcolor_label, bgcolor_entry, bgcolor_selec,
                                  fcolor_label, fcolor_entry, fcolor_selec,
                                  bsgs, bsvb, bsc, bsr, bshb,
                                  cmrg, cmsg, cmhg, cmvg, cmi, cmip_label,
                                  cmip_entry,
                                  color2_label, color2_entry, color2_selec,
                                  embim_check, embim_label, embim_entry)


        self.optMngr0()
        self.optMngr1()
        self.optMngr2()
        mess_entry.focus()
        root.bind("<Control-Return>", self.make)

    def qrmaker(self, *args):
        """Make the QR code according to specifications. Returns PIL
        image of the QR code.
        """
        if self.errcor.get() == "L":
            ec = qrcode.constants.ERROR_CORRECT_L
        elif self.errcor.get() == "M":
            ec = qrcode.constants.ERROR_CORRECT_M
        elif self.errcor.get() == "Q":
            ec = qrcode.constants.ERROR_CORRECT_Q
        elif self.errcor.get() == "H":
            ec = qrcode.constants.ERROR_CORRECT_H
        # set right module drawer and image factory
        if self.ext.get() == ".png":
            im_fac = StyledPilImage
            if self.boxstyle.get() == "square":
                mod_dr = qrcode.image.styles.moduledrawers.SquareModuleDrawer
            elif self.boxstyle.get() == "gapsquare":
                mod_dr = qrcode.image.styles.moduledrawers.GappedSquareModuleDrawer
            elif self.boxstyle.get() == "circle":
                mod_dr = qrcode.image.styles.moduledrawers.CircleModuleDrawer
            elif self.boxstyle.get() == "rounded":
                mod_dr = qrcode.image.styles.moduledrawers.RoundedModuleDrawer
            elif self.boxstyle.get() == "vbars":
                mod_dr = qrcode.image.styles.moduledrawers.VerticalBarsDrawer
            elif self.boxstyle.get() == "hbars":
                mod_dr = qrcode.image.styles.moduledrawers.HorizontalBarsDrawer
        elif self.ext.get() == ".svg":
            im_fac = SvgImage
            if self.boxstyle.get() != "square":
                messagebox.showwarning("Warning - "+self.mbt,
                                       "Change style or extension!")
        if self.cmask.get() == "solid":
            cmask0 = qrcode.image.styles.colormasks.SolidFillColorMask
        elif self.cmask.get() == "rgrad":
            cmask0 = qrcode.image.styles.colormasks.RadialGradiantColorMask
        elif self.cmask.get() == "sgrad":
            cmask0 = qrcode.image.styles.colormasks.SquareGradiantColorMask
        elif self.cmask.get() == "hgrad":
            cmask0 = qrcode.image.styles.colormasks.HorizontalGradiantColorMask
        elif self.cmask.get() == "vgrad":
            cmask0 = qrcode.image.styles.colormasks.VerticalGradiantColorMask
        elif self.cmask.get() == "image":
            cmask0 = qrcode.image.styles.colormasks.ImageColorMask
        qr = qrcode.QRCode(version=self.size.get(), box_size=self.boxsize.get(),
                           border=self.bdsize.get(), image_factory=im_fac,
                           error_correction=ec)
        qr.add_data(self.mess.get())
        qr.make(fit=True)
        if self.ext.get() == ".svg":  # returns PIL svg image
            return qr.make_image()
        else:  # returns PIL png image
            if self.embim.get():
                embimpath=self.embimp.get()
            else:
                embimpath=None
            if self.cmask.get() == "solid":
                colorpack = (eval(self.bgcolor.get()), eval(self.fcolor.get()))
            elif self.cmask.get() == "image":
                colorpack = (eval(self.bgcolor.get()), self.cmipath.get())
            else:
                colorpack = (eval(self.bgcolor.get()), eval(self.fcolor.get()),
                             eval(self.color2.get()))
            return qr.make_image(module_drawer=mod_dr(),
                                 embeded_image_path=embimpath,
                                 color_mask=cmask0(*colorpack))

    def make(self, *args):
        """Function used to save generated image using the qrmaker()
        function."""
        if self.savedir.get() == "":
            chngs = messagebox.askyesno("Overwrite save directory - "+self.mbt,
                                        "You did not specify the saving "
                                        + "directory. Do you want to use "
                                        + "current directory?")
            if chngs:
                self.savedir.set(os.getcwd())
                conti = True
            else:
                messagebox.showwarning("Warning - "+self.mbt,
                                       "No saving path entered! Image not "
                                       +"saved.")
                conti = False
        elif self.collide.get() == "ask":
            listofims = os.listdir(self.savedir.get())
            if self.picname.get()+self.ext.get() in listofims:
                conti = messagebox.askyesno("Overwrite - "+self.mbt,
                                            "Image with this "+
                                            "name already exists within the "
                                            + "specified location. Do you want"
                                            + " to overwrite it?")
            else:
                conti = True
        elif self.collide.get() == "overwrite":
            conti = True
        elif self.collide.get() == "warn & abort":
            conti = False
            messagebox.showwarning("Warning - "+self.mbt,
                                   "Image with this name already exists within"
                                   + " the specified location! QR code genera"
                                   + "tion aborted.")
        if conti:
            img = self.qrmaker()
            img.save(os.path.join(self.savedir.get(),
                                  self.picname.get()+self.ext.get()))
            messagebox.showinfo("Info - "+self.mbt,
                                "QR code created successfully!")

    def optMngr0(self, *args):
        """Manages disabled state of widgets not supported in SVG image format.
        """
        if self.ext.get() == ".svg":
            for i in self.svgrelatedwidgets:
                i.state(["disabled"])
        elif self.ext.get() == ".png":
            for i in self.svgrelatedwidgets:
                i.state(["!disabled"])
            self.optMngr1()
            self.optMngr2()

    def optMngr1(self, *args):
        """Manage disabled state of the embedded image path entry."""
        if self.embim.get():
            self.svgrelatedwidgets[23].state(["!disabled"])
            self.svgrelatedwidgets[22].state(["!disabled"])
        else:
            self.svgrelatedwidgets[23].state(["disabled"])
            self.svgrelatedwidgets[22].state(["disabled"])

    def optMngr2(self, *args):
        """Manages disabled state of second color or image mask path entries.
        """
        if self.cmask.get() == "solid":
            self.svgrelatedwidgets[19].state(["disabled"])
            self.svgrelatedwidgets[18].state(["disabled"])
            self.svgrelatedwidgets[20].state(["disabled"])
            self.svgrelatedwidgets[17].state(["disabled"])
            self.svgrelatedwidgets[16].state(["disabled"])
        elif self.cmask.get() == "image":
            self.svgrelatedwidgets[19].state(["disabled"])
            self.svgrelatedwidgets[18].state(["disabled"])
            self.svgrelatedwidgets[20].state(["disabled"])
            self.svgrelatedwidgets[17].state(["!disabled"])
            self.svgrelatedwidgets[16].state(["!disabled"])
        else:
            self.svgrelatedwidgets[19].state(["!disabled"])
            self.svgrelatedwidgets[18].state(["!disabled"])
            self.svgrelatedwidgets[20].state(["!disabled"])
            self.svgrelatedwidgets[17].state(["disabled"])
            self.svgrelatedwidgets[16].state(["disabled"])

    def loadpresets(self, *args):
        """Loads presets saved in the file specified by presetname variable."""
        # Format of saved presets:
        # <variable name>=<value>\n
        try:
            with open("presets/"+self.presetname.get()+".txt", "r") as read:
                dat = read.readlines()
        except FileNotFoundError:
            messagebox.showwarning("Warning - "+self.mbt,
                                   "Given preset file does not exist! Please "
                                   + "check the name carefully.")
            return
        for i in range(len(self.spvars)):
            dat[i] = dat[i].strip("\n")
            try:
                if type(self.spvars[i].get()) == str:
                    self.spvars[i].set(dat[i][dat[i].find("=")+1:])
                else:
                    self.spvars[i].set(eval(dat[i][dat[i].find("=")+1:]))
            except (ValueError, SyntaxError):
                messagebox.showwarning("Warning - "+self.mbt, "Loading was "
                                       + "interrupted. Check correct value "
                                       + "of:\n"+dat[i]+"\nin the .txt file.")
        self.optMngr0()
        self.optMngr1()
        self.optMngr2()
        messagebox.showinfo("Info - "+self.mbt, "Presets loaded successfully!")

    def savepresets(self, *args):
        """Saves actual presets into the file specified by presetname variable.
        """
        try:
            with open("presets/"+self.presetname.get()+".txt", "r") as read:
                conti = messagebox.askyesno("Overwrite - "+self.mbt,
                                            "Presets with this name already "
                                            + "exist. Do you want to "
                                            + "overwrite them?")
        except FileNotFoundError:
            conti = True
        if conti:
            with open("presets/"+self.presetname.get()+".txt", "w+") as f:
                for i in range(len(self.spvars)):
                    f.write("{}={}\n".format(self.spnames[i],
                                             str(self.spvars[i].get())))
            messagebox.showinfo("Info - "+self.mbt,
                                "Presets saved successfully!")
            self.reloadpresli()

    def delpresets(self, *args):
        """Deletes presets file under name presetname."""
        try:
            with open("presets/"+self.presetname.get()+".txt", "r") as read:
                conti = messagebox.askyesno("Delete presets - "+self.mbt,
                                            "Do you REALL"
                                            + "Y want to delete preset {}?"
                                            .format(self.presetname.get()))
        except FileNotFoundError:
            conti = False
            messagebox.showinfo("Delete presets - "+self.mbt,
                                "There are no presets with name {}."
                                .format(self.presetname.get()))
        if conti:
            os.system("del presets\\{}.txt".format(self.presetname.get()))
            messagebox.showinfo("Delete presets - "+self.mbt,
                                "Presets {} deleted successfully!"
                                .format(self.presetname.get()))
            self.reloadpresli()

    def reloadpresli(self, *args):
        """Reloads the presets list text widget."""
        self.presli_text['state'] = 'normal'
        self.npres = os.listdir("presets/")
        self.presli_text.delete("1.0", "{}.0".format(len(self.npres)+2))
        self.presli_text.config(height=len(self.npres))
        for i in range(len(self.npres)):
            self.presli_text.insert("{}.0".format(i+1), self.npres[i][:-4]+"\n")
        self.presli_text['state'] = 'disabled'

    def clamp(self, x, *args):
        """Used for validation of rgb tuple elements to be between 0 and 255.
        """
        return max(0, min(x, 255))

    def rgb2hex(self, rgbtup, *args):
        """Converts rgb tuple to a hex string."""
        return "#{:02x}{:02x}{:02x}".format(*[self.clamp(i) for i in rgbtup])

    def hex2rgb(self, hexstr, *args):
        """Converts hex string to RGB tuple."""
        hexstr = hexstr.lstrip("#")
        return tuple(int(hexstr[i:i+2], 16) for i in (0, 2, 4))

    def gimmecolorbg(self, *args):
        """Lets you choose a color of the QR Code background."""
        _, hexcode = colorchooser.askcolor(initialcolor=eval(self.bgcolor.get()))
        self.bgcolor.set(str(self.hex2rgb(hexcode)))

    def gimmecolorf(self, *args):
        """Lets you choose a color of the QR Code background."""
        _, hexcode = colorchooser.askcolor(initialcolor=eval(self.fcolor.get()))
        self.fcolor.set(str(self.hex2rgb(hexcode)))

    def gimmecolor2(self, *args):
        """Lets you choose a color of the QR Code background."""
        _, hexcode = colorchooser.askcolor(initialcolor=eval(self.color2.get()))
        self.color2.set(str(self.hex2rgb(hexcode)))


root = Tk()
qrCodeGen(root)
root.mainloop()
