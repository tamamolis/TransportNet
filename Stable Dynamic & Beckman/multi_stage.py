from math import sqrt
import numpy as np
import sinkhorn as skh
import data_handler as dh

best_sink_beta = 7400
net_name = 'data/EMA_net.tntp'
trips_name = 'data/EMA_trips.tntp'
sink_num_iter, sink_eps = 2500, 10**(-3)


def universal_gradient_descent_function(phi_big_oracle, prox_h, primal_dual_oracle,
                                         t_start, L_init = None, max_iter = 1000,
                                         eps = 1e-5, eps_abs = None, verbose = False):

    iter_step = 100
    if L_init is not None:
        L_value = L_init
    else:
        L_value = np.linalg.norm(phi_big_oracle.grad(t_start))
    
    A = 0.0
    t_prev = np.copy(t_start)
    t = None
    
    grad_sum = np.zeros(len(t_start))
    flows_weighted = np.zeros(len(t_start))
    
    duality_gap_init = None

    primal_func_history = []
    dual_func_history = []
    inner_iters_history = []
    duality_gap_history = []
        
    success = False

    # multi-stage

    # print('ugd!', phi_big_oracle.correspondences)

    handler = dh.DataHandler()
    graph_data = handler.GetGraphData(net_name, columns_order=np.array([0, 1, 2, 3, 4]))
    graph_correspondences, total_od_flow = handler.GetGraphCorrespondences(trips_name)

    n = np.max(graph_data['graph_table']['Init node'].as_matrix())
    df = graph_data['graph_table']

    correspondence_matrix = handler.from_dict_to_cor_matr(graph_correspondences, n)
    T = handler.create_C(df, n, column_name='Free Flow Time')

    # C = handler.create_C(df, n, column_name='length')
    # np.savetxt('data/T.csv', T, delimiter=',')

    L = np.nansum(correspondence_matrix, axis=1)
    W = np.nansum(correspondence_matrix, axis=0)

    people_num = np.nansum(L)

    L = handler.distributor_L_W(L)
    W = handler.distributor_L_W(W)

    L = L / np.nansum(L)
    W = W / np.nansum(W)


    for it_counter in range(1, max_iter + 1):

        # corr reconstruction
        s = skh.Sinkhorn(n, L, W, people_num, sink_num_iter, sink_eps)
        cost_matrix = np.nan_to_num(T * best_sink_beta, nan=100)
        rec = s.iterate(cost_matrix)

        sink_correcpondences_dict = handler.from_cor_matrix_to_dict(rec)

        phi_big_oracle.correspondences = sink_correcpondences_dict


        inner_iters_num = 1

        while True:
            alpha = 1 / L_value

            phi_grad_t = phi_big_oracle.grad(t_prev)
            t = prox_h(t_prev - alpha * phi_grad_t, alpha)

            if it_counter == 1 and inner_iters_num == 1:
                flows_weighted = - phi_grad_t
                duality_gap_init = primal_dual_oracle.duality_gap(t, flows_weighted)
                if eps_abs is None:
                    eps_abs = eps * duality_gap_init
                
                if verbose:
                    print('Primal_init = {:g}'.format(primal_dual_oracle.primal_func_value(flows_weighted)))
                    print('Dual_init = {:g}'.format(primal_dual_oracle.dual_func_value(t)))
                    print('Duality_gap_init = {:g}'.format(duality_gap_init))

            left_value = (phi_big_oracle.func(t_prev) + 
                          np.dot(phi_grad_t, t - t_prev) + 
                          0.5 * eps_abs) - phi_big_oracle.func(t)
            right_value = - 0.5 * L_value * np.sum((t - t_prev)**2)
            if left_value >= right_value:
                break
            else:
                L_value *= 2
                inner_iters_num += 1

        L_value /= 2
        
        t_prev = t
        A += alpha
        grad_sum += alpha * phi_grad_t
        flows_weighted = - grad_sum / A
        
        primal_func_value = primal_dual_oracle.primal_func_value(flows_weighted)
        dual_func_value = primal_dual_oracle.dual_func_value(t)
        duality_gap = primal_dual_oracle.duality_gap(t, flows_weighted)
        
        primal_func_history.append(primal_func_value)
        dual_func_history.append(dual_func_value)
        duality_gap_history.append(duality_gap)
        inner_iters_history.append(inner_iters_num)
        
        if duality_gap < eps_abs:
           success = True
           break
        
        if verbose and (it_counter == 1 or (it_counter) % iter_step == 0):
            print('\nIterations number: ' + str(it_counter))
            print('Inner iterations number: ' + str(inner_iters_num))
            print('Primal_func_value = {:g}'.format(primal_func_value))
            print('Dual_func_value = {:g}'.format(dual_func_value))
            print('Duality_gap = {:g}'.format(duality_gap))
            print('Duality_gap / Duality_gap_init = {:g}'.format(duality_gap / duality_gap_init))


        # new T = t creation
        graph_data['graph_table']['Free Flow Time'] = t
        T = handler.create_C(graph_data['graph_table'],
                             n, column_name='Free Flow Time')

            
    result = {'times': t,
              'flows': flows_weighted,
              'iter_num': it_counter,
              'duality_gap_history': duality_gap_history,
              'inner_iters_history': inner_iters_history,
              'primal_func_history': primal_func_history,
              'dual_func_history': dual_func_history,
             }
    
    if success:
        result['res_msg'] = 'success'
    else:
        result['res_msg'] = 'iterations number exceeded'
        
    if verbose:
        if success:
            print('\nSuccess! Iterations number: ' + str(it_counter))
        else:
            print('\nIterations number exceeded!')
        print('Primal_func_value = {:g}'.format(primal_func_value))
        print('Duality_gap / Duality_gap_init = {:g}'.format(duality_gap / duality_gap_init))
        print('Phi_big_oracle elapsed time: {:.0f} sec'.format(phi_big_oracle.time))
    
    return result