"""Aggregation methods."""


import numpy as np
import scipy.sparse as sparse
from pyamg import amg_core
from pyamg.graph import lloyd_cluster

__all__ = ['standard_aggregation', 'naive_aggregation', 'lloyd_aggregation', 'balanced_lloyd_aggregation']


def standard_aggregation(C, Cpts_suggestion=None, renumber=0, modify=None):
    """Compute the sparsity pattern of the tentative prolongator.

    Parameters
    ----------
    C : csr_matrix
        strength of connection matrix

    Returns
    -------
    AggOp : csr_matrix
        aggregation operator which determines the sparsity pattern
        of the tentative prolongator
    Cpts : array
        array of Cpts, i.e., Cpts[i] = root node of aggregate i

    Examples
    --------
    >>> from scipy.sparse import csr_matrix
    >>> from pyamg.gallery import poisson
    >>> from pyamg.aggregation.aggregate import standard_aggregation
    >>> A = poisson((4,), format='csr')   # 1D mesh with 4 vertices
    >>> A.toarray()
    matrix([[ 2., -1.,  0.,  0.],
            [-1.,  2., -1.,  0.],
            [ 0., -1.,  2., -1.],
            [ 0.,  0., -1.,  2.]])
    >>> standard_aggregation(A)[0].toarray() # two aggregates
    matrix([[1, 0],
            [1, 0],
            [0, 1],
            [0, 1]], dtype=int8)
    >>> A = csr_matrix([[1,0,0],[0,1,1],[0,1,1]])
    >>> A.toarray()                      # first vertex is isolated
    matrix([[1, 0, 0],
            [0, 1, 1],
            [0, 1, 1]])
    >>> standard_aggregation(A)[0].toarray() # one aggregate
    matrix([[0],
            [1],
            [1]], dtype=int8)

    See Also
    --------
    amg_core.standard_aggregation

    """
    if not sparse.isspmatrix_csr(C):
        raise TypeError('expected csr_matrix')

    if C.shape[0] != C.shape[1]:
        raise ValueError('expected square matrix')

    index_type = C.indptr.dtype
    num_rows = C.shape[0]

    Tj = np.empty(num_rows, dtype=index_type)  # stores the aggregate #s
    Cpts = np.empty(num_rows, dtype=index_type)  # stores the Cpts

    """
    Permute_rand  = None
    map_back_rand = None
    map_forward_rand = None
    if renumber: #random ordering
        id_new_order = np.arange(C.shape[0])
        np.random.seed(renumber)
        np.random.shuffle(id_new_order)

        row = []; col = []
        map_back_rand = dict()
        map_forward_rand = dict()
        for i, j in enumerate(id_new_order):
            #row.append(j)
            #col.append(i)
            row.append(i)
            col.append(j)
            map_back_rand[i]    = j
            map_forward_rand[j] = i

        row          = np.array(row)
        col          = np.array(col)
        Permute_rand = sparse.coo_matrix((np.ones(len(row)), (row, col)), shape=C.shape).tocsr()
        C            = Permute_rand.T*C*Permute_rand
    """

    Permute_Cpts  = None
    map_back_Cpts = None
    if Cpts_suggestion is not None:
        """
        if renumber: # need to reorder Cpts_suggestion to be consistent with Permute_rand
            Cpts_suggestion = [ map_forward_rand[cpt] for cpt in Cpts_suggestion]
        """
        # default order of DoFs
        id_default   = np.arange(C.shape[0])
        # DoFs missing from default ordered (complement set to Cpts_suggestion)
        id_comp      = np.setdiff1d(id_default, Cpts_suggestion)
        # put the suggested DoFs first
        id_new_order = np.concatenate((Cpts_suggestion, id_comp))
        #print('standard: len(Cpts_suggestion)=', len(Cpts_suggestion))
        #print('id_new_order:\n', id_new_order)
        row = []; col = []
        map_back_Cpts = dict()
        for i, j in enumerate(id_new_order):
            row.append(j)
            col.append(i)
            map_back_Cpts[i] = j

        row          = np.array(row)
        col          = np.array(col)
        Permute_Cpts = sparse.coo_matrix((np.ones(len(row)), (row, col)), shape=C.shape).tocsr()
        C            = Permute_Cpts.T*C*Permute_Cpts

    if modify == None:
        fn = amg_core.standard_aggregation
        num_aggregates = fn(num_rows, C.indptr, C.indices, Tj, Cpts)
    else:
        from pyamg.amg_core.standard_agg_alexey import standard_aggregation_py
        fn = standard_aggregation_py
        num_aggregates,  Tj, Cpts = fn(num_rows, C.indptr, C.indices, Tj, Cpts, modify=modify)
    Cpts = Cpts[:num_aggregates]

    if Cpts_suggestion is not None: # map data back
        for i in range(len(Cpts)):
            Cpts[i] = map_back_Cpts[Cpts[i]]
        Tj = Permute_Cpts*Tj
        C  = Permute_Cpts*C*Permute_Cpts.T

    """
    if renumber: # map data back
        for i in range(len(Cpts)):
            Cpts[i] = map_back_rand[Cpts[i]]
        Tj = Permute_rand*Tj
        C  = Permute_rand*C*Permute_rand.T
    """

    if num_aggregates == 0:
        # return all zero matrix and no Cpts
        return sparse.csr_matrix((num_rows, 1), dtype='int8'),\
            np.array([], dtype=index_type)
    else:

        shape = (num_rows, num_aggregates)
        if Tj.min() == -1:
            # some nodes not aggregated
            mask = Tj != -1
            row = np.arange(num_rows, dtype=index_type)[mask]
            col = Tj[mask]
            data = np.ones(len(col), dtype='int8')
            return sparse.coo_matrix((data, (row, col)), shape=shape).tocsr(), Cpts
        else:
            # all nodes aggregated
            Tp = np.arange(num_rows+1, dtype=index_type)
            Tx = np.ones(len(Tj), dtype='int8')
            return sparse.csr_matrix((Tx, Tj, Tp), shape=shape), Cpts


def naive_aggregation(C):
    """Compute the sparsity pattern of the tentative prolongator.

    Parameters
    ----------
    C : csr_matrix
        strength of connection matrix

    Returns
    -------
    AggOp : csr_matrix
        aggregation operator which determines the sparsity pattern
        of the tentative prolongator
    Cpts : array
        array of Cpts, i.e., Cpts[i] = root node of aggregate i

    Examples
    --------
    >>> from scipy.sparse import csr_matrix
    >>> from pyamg.gallery import poisson
    >>> from pyamg.aggregation.aggregate import naive_aggregation
    >>> A = poisson((4,), format='csr')   # 1D mesh with 4 vertices
    >>> A.toarray()
    matrix([[ 2., -1.,  0.,  0.],
            [-1.,  2., -1.,  0.],
            [ 0., -1.,  2., -1.],
            [ 0.,  0., -1.,  2.]])
    >>> naive_aggregation(A)[0].toarray() # two aggregates
    matrix([[1, 0],
            [1, 0],
            [0, 1],
            [0, 1]], dtype=int8)
    >>> A = csr_matrix([[1,0,0],[0,1,1],[0,1,1]])
    >>> A.toarray()                      # first vertex is isolated
    matrix([[1, 0, 0],
            [0, 1, 1],
            [0, 1, 1]])
    >>> naive_aggregation(A)[0].toarray() # two aggregates
    matrix([[1, 0],
            [0, 1],
            [0, 1]], dtype=int8)

    See Also
    --------
    amg_core.naive_aggregation

    Notes
    -----
    Differs from standard aggregation.  Each dof is considered.  If it has been
    aggregated, skip over.  Otherwise, put dof and any unaggregated neighbors
    in an aggregate.  Results in possibly much higher complexities than
    standard aggregation.

    """
    if not sparse.isspmatrix_csr(C):
        raise TypeError('expected csr_matrix')

    if C.shape[0] != C.shape[1]:
        raise ValueError('expected square matrix')

    index_type = C.indptr.dtype
    num_rows = C.shape[0]

    Tj = np.empty(num_rows, dtype=index_type)  # stores the aggregate #s
    Cpts = np.empty(num_rows, dtype=index_type)  # stores the Cpts

    fn = amg_core.naive_aggregation

    num_aggregates = fn(num_rows, C.indptr, C.indices, Tj, Cpts)
    Cpts = Cpts[:num_aggregates]
    Tj = Tj - 1

    if num_aggregates == 0:
        # all zero matrix
        return sparse.csr_matrix((num_rows, 1), dtype='int8'), Cpts
    else:
        shape = (num_rows, num_aggregates)
        # all nodes aggregated
        Tp = np.arange(num_rows+1, dtype=index_type)
        Tx = np.ones(len(Tj), dtype='int8')
        return sparse.csr_matrix((Tx, Tj, Tp), shape=shape), Cpts


def lloyd_aggregation(C, ratio=0.03, distance='unit', maxiter=10, nCpts_suggestion=None, Cpts_suggestion=None):
    """Aggregate nodes using Lloyd Clustering.

    Parameters
    ----------
    C : csr_matrix
        strength of connection matrix
    ratio : scalar
        Fraction of the nodes which will be seeds.
    distance : ['unit','abs','inv',None]
        Distance assigned to each edge of the graph G used in Lloyd clustering

        For each nonzero value C[i,j]:

        =======  ===========================
        'unit'   G[i,j] = 1
        'abs'    G[i,j] = abs(C[i,j])
        'inv'    G[i,j] = 1.0/abs(C[i,j])
        'same'   G[i,j] = C[i,j]
        'sub'    G[i,j] = C[i,j] - min(C)
        =======  ===========================

    maxiter : int
        Maximum number of iterations to perform

    Returns
    -------
    AggOp : csr_matrix
        aggregation operator which determines the sparsity pattern
        of the tentative prolongator
    seeds : array
        array of Cpts, i.e., Cpts[i] = root node of aggregate i

    See Also
    --------
    amg_core.standard_aggregation

    Examples
    --------
    >>> from scipy.sparse import csr_matrix
    >>> from pyamg.gallery import poisson
    >>> from pyamg.aggregation.aggregate import lloyd_aggregation
    >>> A = poisson((4,), format='csr')   # 1D mesh with 4 vertices
    >>> A.toarray()
    matrix([[ 2., -1.,  0.,  0.],
            [-1.,  2., -1.,  0.],
            [ 0., -1.,  2., -1.],
            [ 0.,  0., -1.,  2.]])
    >>> lloyd_aggregation(A)[0].toarray() # one aggregate
    matrix([[1],
            [1],
            [1],
            [1]], dtype=int8)
    >>> # more seeding for two aggregates
    >>> Agg = lloyd_aggregation(A,ratio=0.5)[0].toarray()

    """
    if ratio <= 0 or ratio > 1:
        raise ValueError('ratio must be > 0.0 and <= 1.0')

    if not (sparse.isspmatrix_csr(C) or sparse.isspmatrix_csc(C)):
        raise TypeError('expected csr_matrix or csc_matrix')

    if distance == 'unit':
        data = np.ones_like(C.data).astype(float)
    elif distance == 'abs':
        data = abs(C.data)
    elif distance == 'inv':
        data = 1.0/abs(C.data)
    elif distance == 'same':
        data = C.data
    elif distance == 'min':
        data = C.data - C.data.min()
    else:
        raise ValueError('unrecognized value distance=%s' % distance)

    if C.dtype == complex:
        data = np.real(data)

    assert(data.min() >= 0)

    G = C.__class__((data, C.indices, C.indptr), shape=C.shape)

    if nCpts_suggestion is not None:
        num_seeds = nCpts_suggestion
    else:
        num_seeds = int(min(max(ratio * G.shape[0], 1), G.shape[0]))

    distances, clusters, seeds = lloyd_cluster(G, num_seeds, maxiter=maxiter,
                                               Cpts_suggestion=Cpts_suggestion)

    #print(num_seeds, len(seeds))
    row = (clusters >= 0).nonzero()[0]
    col = clusters[row]
    data = np.ones(len(row), dtype='int8')
    AggOp = sparse.coo_matrix((data, (row, col)),
                              shape=(G.shape[0], num_seeds)).tocsr()
    return AggOp, seeds


def balanced_lloyd_aggregation(C, num_clusters=None):
    """Aggregate nodes using Balanced Lloyd Clustering.

    Parameters
    ----------
    C : csr_matrix
        strength of connection matrix with positive weights
    num_clusters : int
        Number of seeds or clusters expected (default: C.shape[0] / 10)

    Returns
    -------
    AggOp : csr_matrix
        aggregation operator which determines the sparsity pattern
        of the tentative prolongator
    seeds : array
        array of Cpts, i.e., Cpts[i] = root node of aggregate i

    See Also
    --------
    amg_core.standard_aggregation

    Examples
    --------
    >>> import pyamg
    >>> from pyamg.aggregation.aggregate import balanced_lloyd_aggregation
    >>> data = pyamg.gallery.load_example('unit_square')
    >>> G = data['A']
    >>> xy = data['vertices'][:,:2]
    >>> G.data[:] = np.ones(len(G.data))

    >>> np.random.seed(787888)
    >>> AggOp, seeds = balanced_lloyd_aggregation(G)

    """

    if num_clusters is None:
        num_clusters = int(C.shape[0] / 10)

    if num_clusters < 1 or num_clusters > C.shape[0]:
        raise ValueError('num_clusters must be between 1 and n')

    if not (sparse.isspmatrix_csr(C) or sparse.isspmatrix_csc(C)):
        raise TypeError('expected csr_matrix or csc_matrix')

    if C.data.min() <= 0:
        raise ValueError('positive edge weights required')

    if C.dtype == complex:
        data = np.real(C.data)
    else:
        data = C.data

    G = C.__class__((data, C.indices, C.indptr), shape=C.shape)
    num_nodes = G.shape[0]

    seeds = np.random.permutation(num_nodes)[:num_clusters]
    seeds = seeds.astype(np.int32)
    mv = np.finfo(G.dtype).max
    d = mv * np.ones(num_nodes, dtype=G.dtype)
    d[seeds] = 0

    cm = -1 * np.ones(num_nodes, dtype=np.int32)
    cm[seeds] = seeds

    amg_core.lloyd_cluster_exact(num_nodes,
                                 G.indptr, G.indices, G.data,
                                 num_clusters,
                                 d, cm, seeds)

    col = cm
    row = np.arange(len(cm))
    data = np.ones(len(row), dtype=np.int32)
    AggOp = sparse.coo_matrix((data, (row, col)),
                              shape=(G.shape[0], num_clusters)).tocsr()
    return AggOp, seeds
