package com.adcage.acaicodefree.service;

import com.adcage.acaicodefree.model.dto.app.AppAddRequest;
import com.adcage.acaicodefree.model.dto.app.AppQueryRequest;
import com.adcage.acaicodefree.model.dto.chat.ChatHistoryQueryRequest;
import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.model.vo.chat.ChatHistoryVO;
import com.adcage.acaicodefree.model.vo.chat.ChatSessionVO;
import com.mybatisflex.core.paginate.Page;
import com.adcage.acaicodefree.model.vo.app.AppVO;
import com.mybatisflex.core.query.QueryWrapper;
import com.mybatisflex.core.service.IService;
import com.adcage.acaicodefree.model.entity.App;
import reactor.core.publisher.Flux;

import java.util.List;

/**
 * 应用 服务层。
 *
 * @author adcage
 */
public interface AppService extends IService<App> {

    /**
     * 创建应用
     *
     * @param appAddRequest 创建参数
     * @param loginUser 登录用户
     * @return 应用 id
     */
    Long createApp(AppAddRequest appAddRequest, User loginUser);

    /**
     * 校验应用参数
     *
     * @param app 应用
     * @param add 是否为创建校验
     */
    void validApp(App app, boolean add);

    /**
     * 获取查询条件
     *
     * @param appQueryRequest 查询请求
     * @return 查询条件
     */
    QueryWrapper getQueryWrapper(AppQueryRequest appQueryRequest);

    /**
     * 获取应用封装
     *
     * @param app 应用
     * @return AppVO
     */
    AppVO getAppVO(App app);

    /**
     * 获取应用封装列表
     *
     * @param appList 应用列表
     * @return AppVO 列表
     */
    List<AppVO> getAppVOList(List<App> appList);

    /**
     * 对话生成代码（流式返回）
     *
     * @param appId     应用 ID
     * @param sessionId 会话 ID（为空时由调用方先创建）
     * @param message   用户消息
     * @param loginUser 当前登录用户
     * @return 流式代码生成结果
     */
    Flux<String> chatToGenCode(Long appId, Long sessionId, String message, User loginUser);

    /**
     * 创建对话会话
     *
     * @param appId     应用 ID
     * @param loginUser 当前登录用户
     * @return 会话 ID
     */
    Long createChatSession(Long appId, User loginUser);

    /**
     * 查询应用下的会话列表
     *
     * @param appId     应用 ID
     * @param loginUser 当前登录用户
     * @return 会话列表
     */
    List<ChatSessionVO> listChatSession(Long appId, User loginUser);

    /**
     * 分页查询会话消息
     *
     * @param chatHistoryQueryRequest 查询参数
     * @param loginUser               当前登录用户
     * @return 消息分页数据
     */
    Page<ChatHistoryVO> listChatHistoryByPage(ChatHistoryQueryRequest chatHistoryQueryRequest, User loginUser);

    /**
     * 部署应用
     *
     * @param appId     应用 ID
     * @param loginUser 当前登录用户
     * @return 部署后的访问 URL
     */
    String deployApp(Long appId, User loginUser);

    /**
     * 缓存查询精选应用分页
     *
     * @param pageNum         页码
     * @param pageSize        页大小
     * @param appQueryRequest 查询请求
     * @return 应用分页
     */
    Page<App> listGoodAppPage(long pageNum, long pageSize, AppQueryRequest appQueryRequest);
}
