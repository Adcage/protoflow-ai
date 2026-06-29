package com.adcage.acaicodefree.service;

import com.adcage.acaicodefree.model.dto.app.AppAddRequest;
import com.adcage.acaicodefree.model.dto.app.AppQueryRequest;
import com.adcage.acaicodefree.model.dto.app.MarketplaceQueryRequest;
import com.adcage.acaicodefree.model.dto.chat.ChatHistoryQueryRequest;
import com.adcage.acaicodefree.model.dto.chat.ChatAttachmentInfo;
import com.adcage.acaicodefree.model.entity.User;
import com.adcage.acaicodefree.model.vo.app.MarketplaceAppVO;
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
     * @param message   传递给运行时的用户消息
     * @param displayMessage 展示给用户并落库的消息
     * @param attachments 附件列表
     * @param loginUser 当前登录用户
     * @return 流式代码生成结果
     */
    Flux<String> chatToGenCode(Long appId, Long sessionId, String message, String displayMessage,
                                List<ChatAttachmentInfo> attachments, User loginUser);

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
     * 重命名会话
     *
     * @param sessionId 会话 ID
     * @param title     新标题
     * @param loginUser 当前登录用户
     */
    void renameChatSession(Long sessionId, String title, User loginUser);

    /**
     * 删除会话
     *
     * @param sessionId 会话 ID
     * @param loginUser 当前登录用户
     */
    void deleteChatSession(Long sessionId, User loginUser);

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

    /**
     * 发布应用到探索广场
     *
     * @param appId      应用 ID
     * @param categories 分类列表
     * @param loginUser  登录用户
     * @return 是否成功
     */
    boolean publishApp(Long appId, List<String> categories, User loginUser);

    /**
     * 取消发布应用（从探索广场下架）
     *
     * @param appId     应用 ID
     * @param loginUser 登录用户
     * @return 是否成功
     */
    boolean unpublishApp(Long appId, User loginUser);

    /**
     * 获取所有允许的分类列表
     *
     * @return 分类列表
     */
    List<String> listCategories();

    /**
     * 分页查询探索广场应用
     *
     * @param request 查询请求
     * @return 探索广场应用分页
     */
    Page<MarketplaceAppVO> listMarketplaceAppVOByPage(MarketplaceQueryRequest request);

    /**
     * Fork 应用
     *
     * @param appId     源应用 ID
     * @param loginUser 登录用户
     * @return 新应用 ID
     */
    Long forkApp(Long appId, User loginUser);
}
