import csv
import jinja2
import re
from ntpath import join, isfile
import os
import ntpath
import codecs
import copy

def getElement(l, index):
    try:
        return l[index]
    except:
        return None

def is_contains(l, element_name):
    for d in l:
        if d.getName() == element_name:
            return True
    return False

def is_endswith(s,suffix):
    return s.endswith(suffix)

def is_startswith(s,prefix):
    return s.endswith(prefix)

def semicolonrepl(matchobj):
    if matchobj.group('quote') == ';':
        return matchobj.group(0).replace(';','&semicolon&')
    else:
        return matchobj.group(0)

def filter_replace_all(s, dict):
    for key, value in dict.iteritems():
        s = s.replace(key, value)
    return s

def filter_split(s, delimiter):
    return s.split(delimiter)

def fitler_find_dict(dict_list, name):
    for d in dict_list:
        if d['name'] == name:
            return d
    return

def ssis_proof(inputfn, outputfn=None):
    inputfolder = ntpath.dirname(inputfn)
    with open(inputfn, 'r') as f:
        contents = f.read()
        # Make sure all set catalog statments are properly commentted out for the 
        # SSIS loading framework
        contents = re.sub(r'(?<!--)(-+\s+)?(SET CATALOG )', '--SET CATALOG ', contents, flags=re.IGNORECASE)
        # Make sure all double quotes are escaped
        contents = re.sub(r'(?<!\\)"', r'\"',contents)
        # subsitute any quoted string
        contents = re.sub(r"([\"'])((?:\\\1|\1\1|(?P<quote>;)|(?!\1).)*)\1",semicolonrepl, contents)
        # Putting tokens in single quotes
        contents = re.sub(r"\((.*)\|\|''\)",r"'\1'",contents)
        # Putting tokens in single quotes
        contents = contents.replace(r"\\", r"\\\\")
        # Remove tailing and leading spaces
        contents = contents.strip()
        # Append start and end quote to contents
        contents = '"' + contents + '"'
        name = ntpath.splitext(ntpath.basename(inputfn))
        if outputfn is None:
            outputfn = name[0]+'_SSIS_READY'+name[1]
        if ntpath.dirname(outputfn) == '':
            outputfn = join(inputfolder, outputfn)
    with open(outputfn,'w') as o:
        o.write(contents)
    
class DataTree(dict):
    parent_name_tag = '_parent'
    class_name_tag = '_class'
    name_tag = 'name'
    root_class = 'data'
    root_name = 'root'
    root = {'name':root_name,class_name_tag:root_class}
    
    
    
    def __init__(self, name=None, _class=None, **kwargs):
        if name is not None and _class is not None:
            construct = dict({'name':name, self.class_name_tag:_class},**kwargs)
        else:
            construct = self.root
        dict.__init__(self, construct)
    
    ''' 
    Modifies the existing self. If the class_name provided is not valid,
    return without doing anything.
    '''
    def filter(self, class_name, exclude=False, *names):
        node_list = self.findClassList(class_name)
        if node_list:
            parent_name = node_list[0].getParent()
        else:
            return self
        if exclude:
            result = [n for n in node_list if n.getName() not in names]
        else:
            result = [n for n in node_list if n.getName() in names]
        parent = self.findNode(parent_name)
        parent[class_name+'s'] = result
        return self 
           
    
                
    
    def getName(self):
        return self[self.name_tag]
        
    def findClassList(self, class_name):
        if self.has_key(class_name+'s'):
            return self[class_name+'s']
        else:
            for ck in self.collectionKeys():
                for e in self[ck]:
                    return e.findClassList(class_name)
            
    def findChildPointer(self, collection_key, child_name):
        for i in range(len(self[collection_key])):
            if self[collection_key][i].getName() == child_name:
                return i
            
                
    
    def collectionKeys(self):
        return [k for k in self.keys() if isinstance(self[k], list)]
    
    def addAttribute(self, attributename, value):
        self[attributename] = value
        return self
    
    def setParent(self, value):
        self[self.parent_name_tag] = value
        return self
    
    def getParent(self):
        return self[self.parent_name_tag]
    
    def getClass(self):
        return self['_class']
    
    ''' 
    Finds the node within the tree with the specified value for 'name'.
    Regardless of what the class is. This finds the first occurance of the 
    object.
    '''
    def findNode(self, value):
        if self.getName() == value:
            return self
        else:
            collection_keys = self.collectionKeys()
            if len(collection_keys) == 0:
                return None
            for k in collection_keys:
                l = self[k]
                if len(l) == 0:
                    #base case: no element in the collection
                    return None
                else:
                    for e in l:
                        node = e.findNode(value)
                        if node != None:
                            return node

    def addChild(self, parent_name, child):
        parent = self.findNode(parent_name)
        if parent is None:
            raise GeneratorError("Couldn't find node with name {n} within DataTree.".format(n=parent_name))
        
        existing_child = parent.findNode(child.getName())
        if not parent.has_key(child.getClass()+'s'):
            parent[child.getClass()+'s'] = [child]
        elif existing_child is None:
            parent[child.getClass()+'s'].append(child)
        else:
            i = parent.findChildPointer(child.getClass()+'s',child.getName())
            parent[child.getClass()+'s'][i]= existing_child.merge(child)
        
        return self
            
 
    ''' 
    Returns the merged version of self and t2
    '''
    def merge(self, t2):
        if not (isinstance(self, dict) and isinstance(t2, dict)):
            message = ('t2 must be of type dict.')
            raise GeneratorError(message)        
        if self.getName() != t2.getName():
            message = ('Can\'t merge two tree with different [name]. '
                       'Tree 1 has name {n1}, while tree 2 has name {n2}.'
                       ).format(n1=self.getName(), n2=t2.getName())
            raise GeneratorError(message)
        
        
        collection_keys1 = self.collectionKeys()
        collection_keys2 = t2.collectionKeys()
        
        label_keys1 = [k for k in self.keys() if k not in collection_keys1]
        label_keys2 = [k for k in t2.keys() if k not in collection_keys2]
        
        for l in label_keys2:
            if l not in label_keys1:
                self.addAttribute(l, t2[l])
        
        extra = [k for k in collection_keys2 if not k in collection_keys1]
        
        for ex in extra:
            # Add new collections keys to self first
            self[ex] = []       
        
        # Base case: no keys    
        for k in collection_keys2:
            l1 = self[k]
            l2 = t2[k]
            names1 = [e.getName() for e in l1]
            names2 = [e.getName() for e in l2]
            
            common_name = list(set(names1) & set(names2))
            
            for i in range(len(l1)):
                if l1[i].getName() in common_name:
                    to_merge1 = filterElement(l1, 'name',[l1[i].getName()])[0]
                    to_merge2 = filterElement(l2, 'name',[l1[i].getName()])[0]
                    
                    # Recursion here
                    l1[i] = to_merge1.merge(to_merge2)
            for e in l2:
                if e.getName() not in common_name:
                    l1.append(e)
        
        return self    
'''
Searches for an element within the all the children of the dictionary, including
itself, that has the proper value for the fieldname. Returns the first match.
Pre-condition: d is a properly formed tree, with mandatory 'name' and '_class'
and all elements within one collection is of the same '_class'.
'''    
def filterElement(l, fieldname, values):
    if len(values) == 0:
        return l
    result = []
    for e in l:
        if e[fieldname] in values:
            result.append(e)
    return result






class GeneratorError(Exception):
    pass

class InputFile(object):
    
    
    def __init__(self, filename=None):
        self.output = []
        self.parent_child_map = {}
        self.data = DataTree()
        if filename is not None:
            self.filename = filename
            self.file = codecs.open(filename, 'rU','utf-8')        
            self.processData()
        
    
    def __repr__(self):
        return self.filename
    
    def addOutput(self, output):
        self.output.append(output)
    
    def bindData(self, data):
        self.data = data
    
    def render(self):
        for o in self.output:
            o.render(self.data)
    
    def processData(self):        
        csvReader = csv.reader(self.file)
        raw_header = csvReader.next()
        self.header = []
        
        print raw_header
        
        last_class = ''
        
        for h in raw_header:
            name_list = h.split('.')
            parent_class_name = getElement(name_list, -3)
            class_name = getElement(name_list, -2)
            attribute_name = getElement(name_list, -1)
            
            if class_name is None:
                class_name = last_class
            
            if parent_class_name is None:
                if self.parent_child_map.has_key(class_name):
                    parent_class_name = self.parent_child_map[class_name]
                else:
                    parent_class_name = DataTree.root_class
            
            if self.parent_child_map.has_key(class_name) and \
               self.parent_child_map[class_name] != parent_class_name:
                message = ('Error while attempting to assign parent [{np}] to '
                           '[{c}]. [{c}] already has parrent [{op}]'
                            ).format(np = parent_class_name, \
                                     c = class_name, \
                                     op = self.parent_child_map[class_name])
                raise GeneratorError(message)
            self.parent_child_map[class_name] = parent_class_name
            
            self.header.append([parent_class_name.strip(), class_name.strip(), attribute_name.strip()])
            
        # Header Processed
        
        # Building sapling
        
        for row in csvReader:
            sapling = DataTree()
            object_list = []
            class_name_map = {DataTree.root_class:DataTree.root_name}
            for i in range(len(row)):
                h = self.header[i]
                #h0 - parent, h[1] - class, h[2] - attribute
                value = row[i]
                if h[2] == 'name':
                    class_name_map[h[1]] = value
                    to_append = DataTree(value, h[1]).setParent(class_name_map[h[0]])
                    object_list.append(to_append)
                else:
                    # This assumes the non-name attributes always come after
                    # the name attributes
                    temp_e = [k for k in object_list if k['_class'] == h[1]]
                    e = temp_e[0]
                    e.addAttribute(h[2],value)
            for o in object_list:
                sapling.addChild(o.getParent(),o)
            
            # Merging sapling with main data trunk   
            self.data = self.data.merge(sapling)

class OutputFile(object):
    
    def __init__(self, template_name, filename=None, outputfolder=None):
        self.template_name = template_name
        dirname = os.path.dirname(template_name)
        self.env = jinja2.Environment(loader=jinja2.FileSystemLoader(dirname),\
                                      extensions=["jinja2.ext.do"])
        
        
        self.env.tests['contains'] = is_contains
        self.env.tests['endswith'] = is_endswith
        self.env.tests['startswith'] = is_startswith
        
        self.env.filters['replace_all'] = filter_replace_all
        self.env.filters['split'] = filter_split
        self.env.filters['find_dict'] = fitler_find_dict

        self.env.trim_blocks=True       
        self.env.lstrip_blocks = True
        if filename is None: 
            self.filename = template_name 
        else: 
            self.filename = filename        
            
        if outputfolder is not None:
            self.outputfolder = outputfolder
            self.filename = os.path.join(self.outputfolder, ntpath.basename(self.filename))
        else:
            self.outputfolder = ntpath.dirname(filename)
        self.inputs = []
    
    def addInput(self, input_object):
        self.inputs.append(input_object)
    
    def renderAll(self, misc={}, exclude=False, **filters):
        data = DataTree()
        for i in self.inputs:
            data.merge(i.data)
        
        if len(filters) == 0:
            self.render(data, '')
        else:
            for name, filter in filters.iteritems():
                clone = copy.deepcopy(data)
                for classname, l in filter.iteritems():
                    if type(l) is list and len(l) > 0:
                        clone.filter(classname, exclude, *l)
                self.render(clone, name.replace(" ","_"), misc)
    
    def render(self, data, filtername=None, misc={}):
        basename = os.path.basename(self.template_name)
        self.template = self.env.get_template(basename)
        splitted = self.filename.split('.')
        if filtername is not None and filtername != '':
            splitted.insert(-1,filtername)
        misc['filtername'] = filtername
        filename = '.'.join(splitted)
        with open(filename, 'wb') as outfile:
            print >> outfile, self.template.render(data = data, misc = misc)

    def addFilter(self, func):
        self.env.filters[func.__name__]=func
        
    def applyDataFilter(self, classname, exclude=False, *names):
        for i in self.inputs:
            i.data.filter(classname, exclude, *names)


'''
Utitly method that accepts a string or list of strings of filenames as input
files, and template files, and a output folder, then merges all input files 
together, and produce one output per template into the output folder.
'''
def GenerateOutput(inputfilename, templatename, outputfolder):
    if type(inputfilename) is list and type(templatename) is list:
        inputlist = []
        for i in inputfilename:
            inputlist.append(InputFile(i))
        for t in templatename:
            output_object = OutputFile(t, outputfolder=outputfolder)   
            for input_object in inputlist:
                output_object.addInput(input_object)
            yield output_object
            
    elif type(inputfilename) is str and type(templatename) is str:
        input_object = InputFile(inputfilename)
        output_object = OutputFile(templatename, outputfolder=outputfolder)
        input_object.addOutput(output_object)
        input_object.render()
        yield output_object
    
    elif type(inputfilename) is list and type(templatename) is str:
        output_object = OutputFile(templatename, outputfolder=outputfolder)                
        for i in inputfilename:
            input_object = InputFile(i)
            output_object.addInput(input_object)
        yield output_object
        

    elif type(inputfilename) is str and type(templatename) is list:
        input_object = InputFile(inputfilename)
        for t in templatename:
            output_object = OutputFile(t, outputfolder=outputfolder)                
            output_object.addInput(input_object)
            yield output_object
            
            

def GenerateCode(inputfilename, templatename, outputfolder, exclude=False, misc={}, **tempalate_filters):
    for o in GenerateOutput(inputfilename, templatename, outputfolder):
        f = tempalate_filters.get(ntpath.basename(o.template_name))
        if f is None:
            f = {}
        o.renderAll(misc, exclude, **f)

    
