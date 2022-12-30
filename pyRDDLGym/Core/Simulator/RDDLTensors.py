import datetime
import numpy as np
from typing import Callable, Iterable, List, Set, Tuple, Union

from pyRDDLGym.Core.ErrorHandling.RDDLException import RDDLInvalidNumberOfArgumentsError
from pyRDDLGym.Core.ErrorHandling.RDDLException import RDDLInvalidObjectError
from pyRDDLGym.Core.ErrorHandling.RDDLException import RDDLTypeError

from pyRDDLGym.Core.Compiler.RDDLModel import RDDLModel
from pyRDDLGym.Core.Parser.expr import Value


class RDDLTensors:
    
    INT = np.int64
    REAL = np.float64
        
    NUMPY_TYPES = {
        'int': INT,
        'real': REAL,
        'bool': bool
    }
    
    DEFAULT_VALUES = {
        'int': 0,
        'real': 0.0,
        'bool': False
    }
    
    VALID_SYMBOLS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
    
    def __init__(self, rddl: RDDLModel, debug: bool=False) -> None:
        self.rddl = rddl
        self.debug = debug
        
        # clear the log file
        self.filename = f'debug_{rddl._AST.domain.name}_{rddl._AST.instance.name}.txt'
        if self.debug:
            fp = open(self.filename, 'w')
            fp.write('')
            fp.close()
            
        self.index_of_object, self.grounded = self._compile_objects()
        self.init_values = self._compile_init_values()
        
        self._cached_transforms = {}

    def _compile_objects(self):
        grounded = {}
        for var, types in self.rddl.param_types.items():
            grounded[var] = list(self.rddl.grounded_names(var, types))
        
        index_of_object = {}
        for objects in self.rddl.objects.values():
            for i, obj in enumerate(objects):
                index_of_object[obj] = i  
    
        return index_of_object, grounded
        
    def _compile_init_values(self):
        init_values = {}
        init_values.update(self.rddl.nonfluents)
        init_values.update(self.rddl.init_state)
        init_values.update(self.rddl.actions)
        init_values = {name: value 
                       for name, value in init_values.items() 
                       if value is not None}

        # enum literals are converted to integers
        new_init_values = init_values.copy()
        for name, value in init_values.items():
            var = self.rddl.parse(name)[0]
            prange = self.rddl.variable_ranges[var]
            if prange in self.rddl.enum_types:
                if self.rddl.objects_rev.get(value, None) != prange:
                    raise RDDLInvalidObjectError(
                        f'Literal <{value}> does not belong to enum <{prange}>, '
                        f'must be one of {set(self.rddl.objects[prange])}.')
                new_init_values[name] = self.index_of_object[value]
        init_values = new_init_values
        
        init_arrays = {}
        for var in self.rddl.variable_ranges.keys():
            
            # try to extract a default value if missing for a primitive type
            # enum types are treated as integers
            prange = self.rddl.variable_ranges[var]
            default = RDDLTensors.DEFAULT_VALUES.get(prange, None)
            if default is None:
                if prange in self.rddl.enum_types:
                    prange = 'int'
                    default = 0
                else:
                    raise RDDLTypeError(
                        f'Type <{prange}> of variable <{var}> is not valid, '
                        f'must be an enum type in {self.rddl.enum_types} '
                        f'or one of {set(RDDLTensors.DEFAULT_VALUES.keys())}.')   
            
            # create a tensor filled with init_values
            types = self.rddl.param_types[var]
            dtype = RDDLTensors.NUMPY_TYPES[prange]
            if types:
                if self.rddl.is_grounded:
                    for name in self.rddl.grounded_names(var, types):
                        init_arrays[name] = dtype(init_values.get(name, default)) 
                else:
                    grounded_values = [
                        init_values.get(name, default) 
                        for name in self.rddl.grounded_names(var, types)
                    ]
                    array = np.asarray(grounded_values, dtype=dtype)
                    array = np.reshape(array, newshape=self.shape(types), order='C')
                    init_arrays[var] = array                
            else:
                init_arrays[var] = dtype(init_values.get(var, default))
        
        # log initial values to file
        if self.debug:
            tensor_info = '\n\t'.join(
                (f'{k}{[] if self.rddl.is_grounded else self.rddl.param_types[k]}, '
                 f'shape={v.shape if type(v) is np.ndarray else ()}, '
                 f'dtype={v.dtype if type(v) is np.ndarray else type(v).__name__}')
                for k, v in init_arrays.items())
            self.write_debug_message(
                f'initializing pvariable tensors:' 
                    f'\n\t{tensor_info}\n'
            )
            
        return init_arrays
        
    def coordinates(self, objects: Iterable[str], msg: str='') -> Tuple[int, ...]:
        '''Converts a list of objects into their coordinate representation.
        
        :param objects: object instances corresponding to valid types defined
        in the RDDL domain
        :param msg: an error message to print in case the conversion fails.
        '''
        index_of_obj = self.index_of_object
        try:
            return tuple(index_of_obj[obj] for obj in objects)
        except:
            for obj in objects:
                if obj not in index_of_obj:
                    raise RDDLInvalidObjectError(
                        f'Object <{obj}> is not valid, '
                        f'must be one of {set(index_of_obj.keys())}.\n'
                        f'{msg}')
    
    def shape(self, types: Iterable[str], msg: str='') -> Tuple[int, ...]:
        '''Given a list of RDDL types, returns the shape of a tensor
        that would hold all values of a pvariable with those type arguments
        
        :param types: a list of RDDL types
        :param msg: an error message to print in case the calculation fails
        '''
        objects = self.rddl.objects
        try:
            return tuple(len(objects[ptype]) for ptype in types)
        except:
            for ptype in types:
                if ptype not in objects:
                    raise RDDLInvalidObjectError(
                        f'Type <{ptype}> is not valid, '
                        f'must be one of {set(objects.keys())}.\n'
                        f'{msg}')
            
    def write_debug_message(self, msg: str) -> None:
        if self.debug:
            fp = open(self.filename, 'a')
            timestamp = str(datetime.datetime.now())
            fp.write(timestamp + ': ' + msg + '\n')
            fp.close()
        
    def map(self, var: str,
            obj_in: List[str],
            sign_out: List[Tuple[str, str]],
            literals: List[int],
            gnp=np,
            msg: str='') -> Callable[[np.ndarray], np.ndarray]:
        '''Returns a function that transforms a pvariable value tensor to one
        whose shape matches a desired output signature. This operation is
        achieved by adding new dimensions to the value as needed, and performing
        a combination of transposition/reshape/einsum operations to coerce the 
        value to the desired shape.
        
        :param var: a string pvariable defined in the domain
        :param obj_in: a list of desired object quantifications, e.g. ?x, ?y at
        which var will be evaluated
        :param sign_out: a list of tuples (objecti, typei) representing the
            desired signature of the output pvariable tensor
        :param literals: which indices of obj_in are treated as
            literal (e.g. enum literal or another pvariable) parameters
        :param gnp: the library in which to perform tensor arithmetic 
        (either numpy or jax.numpy)
        :param msg: a stack trace to print for error handling
        '''
                
        # check that the input objects match fluent type definition
        types_in = self.rddl.param_types.get(var, [])
        if obj_in is None:
            obj_in = []
        if len(obj_in) != len(types_in):
            raise RDDLInvalidNumberOfArgumentsError(
                f'Variable <{var}> requires {len(types_in)} parameters, '
                f'got {len(obj_in)}.'
                f'\n{msg}')
        
        # eliminate literals
        old_sign_in = tuple(zip(obj_in, types_in))
        literals = set(literals)
        types_in = [ptype for i, ptype in enumerate(types_in) if i not in literals]
        obj_in = [ptype for i, ptype in enumerate(obj_in) if i not in literals]
        
        # reached limit on number of valid dimensions
        valid_symbols = RDDLTensors.VALID_SYMBOLS
        n_out = len(sign_out)
        if n_out > len(valid_symbols):
            raise RDDLInvalidNumberOfArgumentsError(
                f'At most {len(valid_symbols)} object arguments are supported, '
                f'but variable <{var}> has {n_out} arguments.'
                f'\n{msg}')
        
        # find a map permutation(a,b,c...) -> (a,b,c...) for correct transpose
        sign_in = tuple(zip(obj_in, types_in))
        permutation = [None] * len(obj_in)
        new_dims = []
        for i_out, (o_out, t_out) in enumerate(sign_out):
            new_dim = True
            for i_in, (o_in, t_in) in enumerate(sign_in):
                if o_in == o_out:
                    permutation[i_in] = i_out
                    new_dim = False
                    if t_out != t_in: 
                        raise RDDLInvalidObjectError(
                            f'Argument {i_in + 1} of variable <{var}> '
                            f'expects type <{t_in}>, got <{o_out}> of type <{t_out}>.'
                            f'\n{msg}')
            
            # need to expand the shape of the value array
            if new_dim:
                permutation.append(i_out)
                new_dims.append(len(self.rddl.objects[t_out]))
                
        # safeguard against any free remaining variables not accounted for
        free = {sign_in[i][0] for i, p in enumerate(permutation) if p is None}
        if free:
            raise RDDLInvalidNumberOfArgumentsError(
                f'Variable <{var}> has unresolved parameter(s) {free}.'
                f'\n{msg}')
        
        # compute the mapping function as follows:
        # 1. append new axes to value tensor equal to # of missing variables
        # 2. broadcast new axes to the desired shape (# of objects of each type)
        # 3. rearrange the axes as needed to match the desired variables in order
        #     3a. in most cases, it suffices to use np.transform (cheaper)
        #     3b. in cases where we have a more complex contraction like 
        #         fluent(?x) = matrix(?x, ?x), we will use np.einsum
        in_shape = self.shape(types_in)
        out_shape = in_shape + tuple(new_dims)
        new_axis = tuple(range(len(in_shape), len(out_shape)))
         
        lhs = ''.join(valid_symbols[p] for p in permutation)        
        rhs = valid_symbols[:n_out]
        use_einsum = len(set(lhs)) != len(lhs)
        use_tr = lhs != rhs
        if use_einsum:
            subscripts = lhs + '->' + rhs
        elif use_tr:
            subscripts = tuple(np.argsort(permutation))  # inverse permutation
        else:
            subscripts = None
        
        # check if the tensor transform with the given signature already exists
        # if so, just retrieve it from the cache
        # if not, create it and store it in the cache
        transform_id = f'{new_axis}_{out_shape}_{use_einsum}_{use_tr}_{subscripts}'
        _transform = self._cached_transforms.get(transform_id, None)        
        if _transform is None:
            
            def _transform(arg):
                sample = arg
                if new_axis:
                    sample = gnp.expand_dims(sample, axis=new_axis)
                    sample = gnp.broadcast_to(sample, shape=out_shape)
                if use_einsum:
                    return gnp.einsum(subscripts, sample)
                elif use_tr:
                    return gnp.transpose(sample, axes=subscripts)
                else:
                    return sample
            
            self._cached_transforms[transform_id] = _transform
        
        # write mapping info to log file
        operation = gnp.einsum if use_einsum else (
                        gnp.transpose if use_tr else 'None')
        self.write_debug_message(
            f'computing info for filling missing pvariable arguments:' 
                f'\n\tvar           ={var}'
                f'\n\toriginal args ={old_sign_in}'
                f'\n\tliterals      ={literals}'
                f'\n\tnew args      ={sign_in}'
                f'\n\ttarget args   ={sign_out}'
                f'\n\tnew axes      ={new_axis}'
                f'\n\toperation     ={operation}, subscripts={subscripts}'
                f'\n\tunique op id  ={id(_transform)}\n'
        )
            
        return _transform
    
    def literal_slice(self, var: str, 
                      pvars: List[str],
                      msg: str='') -> Tuple[Set[int], Tuple[Union[int, slice], ...]]:
        '''Given a var and a list of pvariable arguments containing both free 
        and/or enum literals, produces a tuple of slice or int objects that, 
        when indexed into an array of the appropriate shape, produces an array 
        where all literals are evaluated in the array. Also returns a set of 
        indices of pvars that are literals.
        '''
        if pvars is None:
            pvars = []
            
        types_in = self.rddl.param_types.get(var, [])
        if len(pvars) != len(types_in):
            raise RDDLInvalidNumberOfArgumentsError(
                f'Variable <{var}> requires {len(types_in)} parameters, '
                f'got {len(pvars)}.'
                f'\n{msg}')
            
        cached_slices = []
        literals = set()
        for i, pvar in enumerate(pvars):
            if pvar in self.rddl.enum_literals:
                enum_type = self.rddl.objects_rev[pvar]
                if types_in[i] != enum_type: 
                    raise RDDLInvalidObjectError(
                        f'Argument {i + 1} of variable <{var}> '
                        f'expects type <{types_in[i]}>, '
                        f'got <{pvar}> of type <{enum_type}>.'
                        f'\n{msg}')
                slice_object = self.index_of_object[pvar]
                literals.add(i)
            else:
                slice_object = slice(None)
            cached_slices.append(slice_object)
        cached_slices = tuple(cached_slices)
        return cached_slices, literals
        
    def expand(self, var: str, values: np.ndarray) -> Iterable[Tuple[str, Value]]:
        '''Produces a grounded representation of the pvariable var from its 
        tensor representation. The output is a dict whose keys are grounded
        representations of the var, and values are read from the tensor.
        
        :param var: the pvariable
        :param values: the tensor whose values correspond to those of var(?...)        
        '''
        keys = self.grounded[var]
        values = np.ravel(values)
        if len(keys) != values.size:
            raise RDDLInvalidNumberOfArgumentsError(
                f'Size of value array is not compatible with variable <{var}>.')
        return zip(keys, values)
